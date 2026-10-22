import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import httpx
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


PLATFORMS: List[Dict[str, Any]] = [
    {
        "name": "GitHub",
        "url": "https://github.com/{}",
        "check_url": "https://api.github.com/users/{}",
        "type": "api",
        "category": "code",
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/{}",
        "check_url": "https://gitlab.com/{}",
        "type": "status",
        "category": "code",
    },
    {
        "name": "Codeberg",
        "url": "https://codeberg.org/{}",
        "check_url": "https://codeberg.org/{}",
        "type": "status",
        "category": "code",
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{}",
        "check_url": "https://www.reddit.com/user/{}/about.json",
        "type": "api",
        "category": "social",
    },
    {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/user?id={}",
        "check_url": "https://hacker-news.firebaseio.com/v0/user/{}.json",
        "type": "api",
        "category": "tech",
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{}",
        "check_url": "https://t.me/{}",
        "type": "status",
        "category": "messaging",
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/{}",
        "check_url": "https://keybase.io/_/api/1.0/user/lookup.json?usernames={}",
        "type": "api",
        "category": "crypto",
    },
    {
        "name": "DevTo",
        "url": "https://dev.to/{}",
        "check_url": "https://dev.to/api/users/by_username?url={}",
        "type": "api",
        "category": "blog",
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{}",
        "check_url": "https://medium.com/@{}",
        "type": "status",
        "category": "blog",
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/u/{}",
        "check_url": "https://hub.docker.com/v2/users/{}",
        "type": "api",
        "category": "tech",
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{}/",
        "check_url": "https://www.pinterest.com/{}/",
        "type": "status",
        "category": "social",
    },
    {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{}",
        "check_url": "https://soundcloud.com/{}",
        "type": "status",
        "category": "audio",
    },
    {
        "name": "Steam",
        "url": "https://steamcommunity.com/id/{}",
        "check_url": "https://steamcommunity.com/id/{}",
        "type": "status",
        "category": "gaming",
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/{}",
        "check_url": "https://vimeo.com/{}",
        "type": "status",
        "category": "video",
    },
    {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/wiki/User:{}",
        "check_url": "https://en.wikipedia.org/wiki/User:{}",
        "type": "status",
        "category": "wiki",
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{}/",
        "check_url": "https://pypi.org/user/{}/",
        "type": "status",
        "category": "code",
    },
    {
        "name": "NPM",
        "url": "https://www.npmjs.com/~{}",
        "check_url": "https://www.npmjs.com/~{}",
        "type": "status",
        "category": "code",
    },
    {
        "name": "MastodonSocial",
        "url": "https://mastodon.social/@{}",
        "check_url": "https://mastodon.social/@{}",
        "type": "status",
        "category": "fediverse",
    },
    {
        "name": "Pastebin",
        "url": "https://pastebin.com/u/{}",
        "check_url": "https://pastebin.com/u/{}",
        "type": "status",
        "category": "text",
    },
    {
        "name": "Kaggle",
        "url": "https://www.kaggle.com/{}",
        "check_url": "https://www.kaggle.com/{}",
        "type": "status",
        "category": "data",
    },
]


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
        username = seed.name.strip().lstrip("@")
        logs: List[str] = [f"Startar användarnamnskanning för '{username}' över {len(PLATFORMS)} plattformar..."]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []
        found_profiles: List[Dict[str, Any]] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
        }

        sem = asyncio.Semaphore(8)

        async def check_platform(client: httpx.AsyncClient, p: Dict[str, Any]):
            check_url = p["check_url"].format(username)
            profile_url = p["url"].format(username)
            async with sem:
                try:
                    resp = await client.get(check_url, headers=headers, follow_redirects=True)
                    exists = False

                    if p["type"] == "api":
                        if resp.status_code == 200:
                            data = resp.json()
                            if p["name"] == "Keybase":
                                exists = bool(
                                    data.get("them") and len(data["them"]) > 0 and data["them"][0] is not None
                                )
                            elif p["name"] == "HackerNews":
                                exists = bool(data and data.get("id"))
                            elif p["name"] == "Reddit":
                                exists = not bool(data.get("error"))
                            else:
                                exists = True
                    else:
                        if resp.status_code == 200:
                            # Kontrollera att inte 404-text finns i innehållet
                            text_lower = resp.text[:2000].lower()
                            if (
                                "page not found" not in text_lower
                                and "user not found" not in text_lower
                                and "doesn't exist" not in text_lower
                            ):
                                exists = True

                    if exists:
                        return {
                            "platform": p["name"],
                            "profile_url": profile_url,
                            "category": p["category"],
                            "status_code": resp.status_code,
                        }
                except Exception:
                    pass
            return None

        async with httpx.AsyncClient(timeout=4.5) as client:
            tasks = [check_platform(client, p) for p in PLATFORMS]
            results = await asyncio.gather(*tasks)

        for res in results:
            if res:
                found_profiles.append(res)
                logs.append(f"Identifierad profil på {res['platform']}: {res['profile_url']}")

        # Skapa bevispost
        case_id = seed.case_id or "default_case"
        clean_user = "".join([c if c.isalnum() else "_" for c in username])
        scan_payload = {
            "username": username,
            "platforms_checked": len(PLATFORMS),
            "found_count": len(found_profiles),
            "profiles": found_profiles,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"footprint_{clean_user}_{int(time.time())}.json",
            data_dict=scan_payload,
            subfolder="social",
        )
        evidence = EvidenceItem(
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
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url=f"osint://username/{username}",
            sha256=sha256_hash,
            note=f"Identifierat via {self.display_name}",
        )

        # Skapa noder och relationer för varje hittad profil
        for prof in found_profiles:
            plat_name = prof["platform"]
            prof_url = prof["profile_url"]
            account_entity = Entity(
                type=EntityType.USERNAME,
                name=f"{username}@{plat_name.lower()}",
                aliases=[username],
                attributes={
                    "platform": plat_name,
                    "url": prof_url,
                    "category": prof["category"],
                    "handle": username,
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
                    attributes={"platform": plat_name, "profile_url": prof_url},
                    provenance=[prov],
                    case_id=seed.case_id,
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
