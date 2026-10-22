import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, TypedDict
import httpx
from app.config import is_mock_osint
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


class MockPlatform(TypedDict):
    name: str
    url: str
    check_url: str
    category: str
    status_code: int
    body: bytes
    content_type: str


PLATFORMS: List[Dict[str, Any]] = [
    {
        "name": "GitHub",
        "url": "https://github.com/{}",
        "check_url": "https://api.github.com/users/{}",
        "category": "code",
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/{}",
        "check_url": "https://gitlab.com/api/v4/users?username={}",
        "category": "code",
    },
    {
        "name": "Codeberg",
        "url": "https://codeberg.org/{}",
        "check_url": "https://codeberg.org/api/v1/users/{}",
        "category": "code",
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{}",
        "check_url": "https://www.reddit.com/user/{}/about.json",
        "category": "social",
    },
    {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/user?id={}",
        "check_url": "https://hacker-news.firebaseio.com/v0/user/{}.json",
        "category": "tech",
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{}",
        "check_url": "https://t.me/{}",
        "category": "messaging",
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/{}",
        "check_url": "https://keybase.io/_/api/1.0/user/lookup.json?usernames={}",
        "category": "crypto",
    },
    {
        "name": "DevTo",
        "url": "https://dev.to/{}",
        "check_url": "https://dev.to/api/users/by_username?url={}",
        "category": "blog",
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{}",
        "check_url": "https://medium.com/@{}",
        "category": "blog",
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/u/{}",
        "check_url": "https://hub.docker.com/v2/users/{}",
        "category": "tech",
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{}/",
        "check_url": "https://www.pinterest.com/{}/",
        "category": "social",
    },
    {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{}",
        "check_url": "https://soundcloud.com/{}",
        "category": "audio",
    },
    {
        "name": "Steam",
        "url": "https://steamcommunity.com/id/{}",
        "check_url": "https://steamcommunity.com/id/{}",
        "category": "gaming",
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/{}",
        "check_url": "https://vimeo.com/{}",
        "category": "video",
    },
    {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/wiki/User:{}",
        "check_url": "https://en.wikipedia.org/w/api.php?action=query&list=users&ususers={}&format=json",
        "category": "wiki",
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{}/",
        "check_url": "https://pypi.org/user/{}/",
        "category": "code",
    },
    {
        "name": "NPM",
        "url": "https://www.npmjs.com/~{}",
        "check_url": "https://www.npmjs.com/~{}",
        "category": "code",
    },
    {
        "name": "MastodonSocial",
        "url": "https://mastodon.social/@{}",
        "check_url": "https://mastodon.social/api/v1/accounts/lookup?acct={}",
        "category": "fediverse",
    },
    {
        "name": "Pastebin",
        "url": "https://pastebin.com/u/{}",
        "check_url": "https://pastebin.com/u/{}",
        "category": "text",
    },
    {
        "name": "Kaggle",
        "url": "https://www.kaggle.com/{}",
        "check_url": "https://www.kaggle.com/{}",
        "category": "data",
    },
]


def validate_probe_response(platform_name: str, username: str, resp: httpx.Response) -> bool:
    """
    Verifierar huruvida ett konto faktiskt existerar baserat på
    WhatsMyName-regler och bekräftande svarskriterier.
    """
    if resp.status_code != 200:
        return False

    uname_lower = username.lower()
    text = resp.text
    text_lower = text.lower()

    generic_error_phrases = [
        "page not found",
        "user not found",
        "profile not found",
        "doesn't exist",
        "does not exist",
        "account not found",
        "404 not found",
        "the page you requested could not be found",
        "we couldn't find that page",
    ]

    if platform_name == "GitHub":
        try:
            data = resp.json()
            return isinstance(data, dict) and data.get("login", "").lower() == uname_lower
        except Exception:
            return "user-profile" in text_lower or f"/{uname_lower}" in text_lower

    elif platform_name == "GitLab":
        try:
            data = resp.json()
            if isinstance(data, list):
                return any(isinstance(u, dict) and u.get("username", "").lower() == uname_lower for u in data)
        except Exception:
            pass
        return any(phrase in text_lower for phrase in ["user-profile", "user-avatar"]) and not any(
            err in text_lower for err in generic_error_phrases
        )

    elif platform_name == "HackerNews":
        try:
            data = resp.json()
            return isinstance(data, dict) and bool(data.get("id"))
        except Exception:
            return False

    elif platform_name == "Keybase":
        try:
            data = resp.json()
            return (
                isinstance(data, dict)
                and data.get("status", {}).get("code") == 0
                and bool(data.get("them") and len(data["them"]) > 0 and data["them"][0] is not None)
            )
        except Exception:
            return False

    elif platform_name == "Reddit":
        try:
            data = resp.json()
            return isinstance(data, dict) and data.get("kind") == "t2" and not data.get("error")
        except Exception:
            return False

    elif platform_name == "DevTo":
        try:
            data = resp.json()
            return isinstance(data, dict) and data.get("username", "").lower() == uname_lower
        except Exception:
            return False

    elif platform_name == "DockerHub":
        try:
            data = resp.json()
            return isinstance(data, dict) and data.get("username", "").lower() == uname_lower
        except Exception:
            return False

    elif platform_name == "Codeberg":
        try:
            data = resp.json()
            return isinstance(data, dict) and data.get("username", "").lower() == uname_lower
        except Exception:
            return False

    elif platform_name == "Wikipedia":
        try:
            data = resp.json()
            users = data.get("query", {}).get("users", [])
            return len(users) > 0 and "missing" not in users[0] and bool(users[0].get("userid"))
        except Exception:
            return False

    elif platform_name == "MastodonSocial":
        try:
            data = resp.json()
            return isinstance(data, dict) and data.get("username", "").lower() == uname_lower
        except Exception:
            return False

    elif platform_name == "Telegram":
        # Telegram returnerar 200 även när användaren saknas.
        # Saknas användaren är og:title = "Telegram: Contact @username" och saknar profilinfo.
        if "tgme_page_icon" in text and "tgme_page_extra" not in text and "tgme_page_title" not in text:
            return False
        if f"telegram: contact @{uname_lower}" in text_lower and "tgme_page_extra" not in text_lower:
            return False
        return "tgme_page_title" in text or "tgme_page_extra" in text or "tgme_action_button_new" in text

    elif platform_name == "Steam":
        # Steam returnerar 200 men anger feltext i brödtexten
        if "the specified profile could not be found" in text_lower:
            return False
        return any(m in text for m in ["actual_persona_name", "playerAvatar", "profile_header"])

    elif platform_name == "Pinterest":
        if any(err in text_lower for err in ["resourcenotfound", "user not found", "page not found"]):
            return False
        return "__pws_data__" in text_lower or f"pinterest.com/{uname_lower}" in text_lower

    elif platform_name == "PyPI":
        if any(err in text_lower for err in generic_error_phrases):
            return False
        return "user-profile" in text or "packages by" in text_lower

    elif platform_name == "Kaggle":
        if any(err in text_lower for err in generic_error_phrases):
            return False
        return not any(err in text_lower for err in ["user not found", "page not found"])

    # Generell kontroll
    for err in generic_error_phrases:
        if err in text_lower[:2500]:
            return False

    return True


class SocialFootprintTransform(BaseTransform):
    name = "social_footprint_transform"
    display_name = "Social Footprint & Username Enumerator"
    description = (
        "Söker igenom 20+ offentliga webbtjänster och plattformar efter matchande användarnamn och digitala fotspår."
    )
    category = "social"
    supported_types: Set[EntityType] = {EntityType.USERNAME, EntityType.PERSON}

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        raw_name = seed.name.strip().lstrip("@")
        if "@" in raw_name and not raw_name.startswith("@"):
            raw_name = raw_name.split("@")[0]

        # Normalisera användarnamn (ta bort mellanslag och otillåtna URL-tecken)
        username = re.sub(r"\s+", "", raw_name)
        if not username:
            return TransformResult(
                transform_name=self.name,
                success=False,
                seed_id=seed.id,
                error_message="Ogiltigt eller tomt användarnamn för profilundersökning.",
                execution_time_seconds=time.time() - start_time,
            )

        case_id = seed.case_id or "default_case"
        clean_user = "".join([c if c.isalnum() else "_" for c in username])
        logs: List[str] = [f"Startar användarnamnskanning för '{username}' över {len(PLATFORMS)} plattformar..."]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []
        found_profiles: List[Dict[str, Any]] = []

        # ----------------------------------------------------------------------
        # MOCK-LÄGE (vid automatiserade enhetstester med pytest eller MOCK_OSINT=true)
        # ----------------------------------------------------------------------
        if is_mock_osint():
            logs.append("[MOCK_OSINT] Testläge aktivt - genererar deterministiska mock-profiler för testmiljö.")
            mock_targets: List[MockPlatform] = [
                {
                    "name": "GitHub",
                    "url": f"https://github.com/{username}",
                    "check_url": f"https://api.github.com/users/{username}",
                    "category": "code",
                    "status_code": 200,
                    "body": json.dumps({"login": username, "id": 10101, "type": "User"}).encode("utf-8"),
                    "content_type": "application/json",
                },
                {
                    "name": "GitLab",
                    "url": f"https://gitlab.com/{username}",
                    "check_url": f"https://gitlab.com/api/v4/users?username={username}",
                    "category": "code",
                    "status_code": 200,
                    "body": json.dumps([{"username": username, "id": 20202, "name": username}]).encode("utf-8"),
                    "content_type": "application/json",
                },
            ]

            for m in mock_targets:
                plat_clean = "".join([c if c.isalnum() else "_" for c in m["name"]]).lower()
                rel_path, sha256_hash, size = object_store.store_bytes(
                    case_id=case_id,
                    filename=f"probe_{plat_clean}_{clean_user}_{int(time.time())}.bin",
                    data=m["body"],
                    subfolder="social_probes",
                )

                evidence = EvidenceItem(
                    case_id=case_id,
                    title=f"Verified profile HTTP probe (Mock): {m['name']} ({username})",
                    file_path=rel_path,
                    file_size_bytes=size,
                    mime_type=m["content_type"],
                    sha256=sha256_hash,
                    source_url=m["url"],
                    collector_plugin=self.name,
                    metadata={"platform": m["name"], "status_code": 200, "mock": True},
                )
                evidence_items.append(evidence)

                prov = self.create_provenance(
                    source_url=m["url"],
                    sha256=sha256_hash,
                    note="Bekräftad profil via WhatsMyName-probe (Mock)",
                )

                account_entity = Entity(
                    type=EntityType.USERNAME,
                    name=f"{username}@{m['name'].lower()}",
                    aliases=[username],
                    attributes={
                        "platform": m["name"],
                        "url": m["url"],
                        "category": m["category"],
                        "handle": username,
                        "verified": True,
                        "http_status": 200,
                        "sha256": sha256_hash,
                    },
                    provenance=[prov],
                    case_id=seed.case_id,
                )
                new_entities.append(account_entity)
                new_relationships.append(
                    Relationship(
                        source_id=seed.id,
                        target_id=account_entity.id,
                        relation_type=RelationshipType.HAS_ALIAS,
                        attributes={"platform": m["name"], "profile_url": m["url"]},
                        provenance=[prov],
                        case_id=seed.case_id,
                    )
                )
                found_profiles.append(
                    {
                        "platform": m["name"],
                        "profile_url": m["url"],
                        "category": m["category"],
                        "status_code": 200,
                        "sha256": sha256_hash,
                    }
                )

            # Spara övergripande rapport
            scan_payload = {
                "username": username,
                "platforms_checked": len(PLATFORMS),
                "found_count": len(found_profiles),
                "profiles": found_profiles,
                "mock_mode": True,
                "scanned_at": datetime.now(timezone.utc).isoformat(),
            }
            rel_path, sha256_hash, size = object_store.store_json(
                case_id=case_id,
                filename=f"footprint_{clean_user}_{int(time.time())}.json",
                data_dict=scan_payload,
                subfolder="social",
            )
            evidence_items.append(
                EvidenceItem(
                    case_id=case_id,
                    title=f"Social Footprint scan summary for '{username}'",
                    file_path=rel_path,
                    file_size_bytes=size,
                    mime_type="application/json",
                    sha256=sha256_hash,
                    source_url=f"osint://username/{username}",
                    collector_plugin=self.name,
                    metadata={"username": username, "matches": len(found_profiles), "mock": True},
                )
            )

            exec_time = time.time() - start_time
            logs.append(
                f"Mock social footprint-analys klar på {exec_time:.2f}s. {len(found_profiles)} profiler bekräftade."
            )
            return TransformResult(
                transform_name=self.name,
                success=True,
                seed_id=seed.id,
                entities=new_entities,
                relationships=new_relationships,
                evidence_items=evidence_items,
                execution_time_seconds=exec_time,
                logs=logs,
            )

        # ----------------------------------------------------------------------
        # SKARPT LÄGE: Asynkrona HTTP-prober mot etablerade WhatsMyName-endpoints
        # ----------------------------------------------------------------------
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
        }
        sem = asyncio.Semaphore(8)

        async def check_platform(client: httpx.AsyncClient, p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            check_url = p["check_url"].format(username)
            profile_url = p["url"].format(username)
            async with sem:
                try:
                    resp = await client.get(check_url, headers=headers, follow_redirects=True)
                    if validate_probe_response(p["name"], username, resp):
                        return {
                            "platform": p["name"],
                            "profile_url": profile_url,
                            "check_url": check_url,
                            "category": p["category"],
                            "status_code": resp.status_code,
                            "raw_bytes": resp.content,
                            "content_type": resp.headers.get("content-type", "application/octet-stream").split(";")[0],
                        }
                except Exception:
                    pass
            return None

        async with httpx.AsyncClient(timeout=4.5) as client:
            tasks = [check_platform(client, p) for p in PLATFORMS]
            results = await asyncio.gather(*tasks)

        for res in results:
            if res:
                raw_bytes = res["raw_bytes"]
                sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
                plat_clean = "".join([c if c.isalnum() else "_" for c in res["platform"]]).lower()

                # Spara det faktiska HTTP-svaret i beviskedjan (object_store) med korrekt SHA-256-hash
                rel_path, stored_sha256, size = object_store.store_bytes(
                    case_id=case_id,
                    filename=f"probe_{plat_clean}_{clean_user}_{int(time.time())}.bin",
                    data=raw_bytes,
                    subfolder="social_probes",
                )

                evidence = EvidenceItem(
                    case_id=case_id,
                    title=f"Verified profile HTTP probe: {res['platform']} ({username})",
                    file_path=rel_path,
                    file_size_bytes=size,
                    mime_type=res["content_type"],
                    sha256=stored_sha256,
                    source_url=res["profile_url"],
                    collector_plugin=self.name,
                    metadata={
                        "platform": res["platform"],
                        "status_code": res["status_code"],
                        "check_url": res["check_url"],
                        "profile_url": res["profile_url"],
                        "sha256": stored_sha256,
                    },
                )
                evidence_items.append(evidence)

                prov = self.create_provenance(
                    source_url=res["profile_url"],
                    sha256=stored_sha256,
                    note=f"Bekräftad profil via WhatsMyName-probe (HTTP {res['status_code']})",
                )

                account_entity = Entity(
                    type=EntityType.USERNAME,
                    name=f"{username}@{res['platform'].lower()}",
                    aliases=[username],
                    attributes={
                        "platform": res["platform"],
                        "url": res["profile_url"],
                        "category": res["category"],
                        "handle": username,
                        "verified": True,
                        "http_status": res["status_code"],
                        "sha256": stored_sha256,
                    },
                    provenance=[prov],
                    case_id=seed.case_id,
                )
                new_entities.append(account_entity)
                new_relationships.append(
                    Relationship(
                        source_id=seed.id,
                        target_id=account_entity.id,
                        relation_type=RelationshipType.HAS_ALIAS,
                        attributes={"platform": res["platform"], "profile_url": res["profile_url"]},
                        provenance=[prov],
                        case_id=seed.case_id,
                    )
                )

                found_profiles.append(
                    {
                        "platform": res["platform"],
                        "profile_url": res["profile_url"],
                        "category": res["category"],
                        "status_code": res["status_code"],
                        "sha256": stored_sha256,
                    }
                )
                logs.append(f"Bekräftad profil på {res['platform']}: {res['profile_url']} (HTTP {res['status_code']})")

        # Spara sammanfattande footprint-rapport i beviskedjan
        scan_payload = {
            "username": username,
            "platforms_checked": len(PLATFORMS),
            "found_count": len(found_profiles),
            "profiles": found_profiles,
            "mock_mode": False,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"footprint_{clean_user}_{int(time.time())}.json",
            data_dict=scan_payload,
            subfolder="social",
        )
        evidence_items.append(
            EvidenceItem(
                case_id=case_id,
                title=f"Social Footprint report for username '{username}'",
                file_path=rel_path,
                file_size_bytes=size,
                mime_type="application/json",
                sha256=sha256_hash,
                source_url=f"osint://username/{username}",
                collector_plugin=self.name,
                metadata={"username": username, "matches": len(found_profiles)},
            )
        )

        exec_time = time.time() - start_time
        logs.append(f"Social footprint-analys klar på {exec_time:.2f}s. {len(found_profiles)} profiler bekräftade.")

        return TransformResult(
            transform_name=self.name,
            success=True,
            seed_id=seed.id,
            entities=new_entities,
            relationships=new_relationships,
            evidence_items=evidence_items,
            execution_time_seconds=exec_time,
            logs=logs,
        )
