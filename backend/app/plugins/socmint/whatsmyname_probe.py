import asyncio
from typing import Any, Dict, List, Optional
import httpx
from app.config import is_mock_osint
from app.plugins.base import (
    BaseOSINTPlugin,
    EntityOutput,
    PluginCategory,
    PluginResult,
    RelationOutput,
)

# Standardiserade WhatsMyName-webbplatser för asynkrona kontroller
TARGET_SITES: List[Dict[str, Any]] = [
    {
        "name": "GitHub",
        "uri_check": "https://api.github.com/users/{account}",
        "profile_url": "https://github.com/{account}",
        "check_type": "status_code",
        "valid_code": 200,
        "category": "developer",
    },
    {
        "name": "GitLab",
        "uri_check": "https://gitlab.com/{account}",
        "profile_url": "https://gitlab.com/{account}",
        "check_type": "status_code",
        "valid_code": 200,
        "category": "developer",
    },
    {
        "name": "Reddit",
        "uri_check": "https://www.reddit.com/user/{account}/about.json",
        "profile_url": "https://www.reddit.com/user/{account}",
        "check_type": "status_code",
        "valid_code": 200,
        "category": "social",
    },
    {
        "name": "HackerNews",
        "uri_check": "https://hacker-news.firebaseio.com/v0/user/{account}.json",
        "profile_url": "https://news.ycombinator.com/user?id={account}",
        "check_type": "status_code",
        "valid_code": 200,
        "category": "developer",
    },
    {
        "name": "Telegram",
        "uri_check": "https://t.me/{account}",
        "profile_url": "https://t.me/{account}",
        "check_type": "status_code",
        "valid_code": 200,
        "category": "messaging",
    },
]


class WhatsMyNameProbe(BaseOSINTPlugin):
    """
    SOCMINT Username Enumeration Probe baserad på WhatsMyName-specifikationen.
    Kör parallella asynkrona sonderingar med konfigurerad timeout (max 4s per probe).
    Skapar endast noder om kontot bekräftas existera.
    """

    plugin_id = "socmint_whatsmyname"
    name = "WhatsMyName Username Enumeration"
    category = PluginCategory.SOCMINT
    nato_admiralty = "B2"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Username", "Person", "Alias", "username", "person", "alias"]

    slug = "socmint_whatsmyname"
    description = "Identifierar digitala fotspår och användarnamn över sociala medier och utvecklarplattformar."
    version = "1.0.0"
    output_entities = ["account", "platform"]
    rate_limit_per_minute = 120
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        username = target.strip().lstrip("@")
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            # Deterministisk mock-data för automatiserade tester
            mock_hits = [
                {"site": "GitHub", "url": f"https://github.com/{username}", "category": "developer"},
                {"site": "Reddit", "url": f"https://www.reddit.com/user/{username}", "category": "social"},
                {"site": "HackerNews", "url": f"https://news.ycombinator.com/user?id={username}", "category": "news"},
            ]
            for hit in mock_hits:
                site_name = hit["site"]
                profile_url = hit["url"]
                account_id = f"{site_name.lower()}:{username}"

                entities.append(
                    EntityOutput(
                        entity_type="account",
                        value=account_id,
                        attributes={
                            "site": site_name,
                            "url": profile_url,
                            "username": username,
                            "category": hit["category"],
                            "verified": True,
                        },
                        confidence_score=0.9,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=username,
                        target_value=account_id,
                        relation_type="HAS_ACCOUNT",
                        attributes={"site": site_name, "admiralty": self.nato_admiralty},
                    )
                )

            raw_payload = {
                "target": username,
                "matches": mock_hits,
                "total_checked": len(TARGET_SITES),
                "total_found": len(mock_hits),
                "mock": True,
            }
            return PluginResult(
                entities=entities,
                relationships=relationships,
                raw_payload=raw_payload,
                nato_admiralty=self.nato_admiralty,
                cost_usd=self.cost_per_query_usd,
            )

        # Skarpt läge: kör parallella httpx-sonderingar
        sem = asyncio.Semaphore(5)

        async def probe_site(site: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            url = site["uri_check"].format(account=username)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IntelNexus/1.0",
                "Accept": "text/html,application/json,*/*",
            }
            async with sem:
                try:
                    resp = await opsec_client.get(url, headers=headers, timeout=4.0)
                    if resp.status_code == site["valid_code"]:
                        if site["name"] == "HackerNews":
                            body = resp.text.strip()
                            if body == "null" or not body:
                                return None
                        return {
                            "site": site["name"],
                            "url": site["profile_url"].format(account=username),
                            "category": site["category"],
                            "status_code": resp.status_code,
                        }
                except Exception:
                    pass
            return None

        tasks = [probe_site(site) for site in TARGET_SITES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        confirmed_hits: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, dict) and r is not None:
                confirmed_hits.append(r)
                site_name = r["site"]
                profile_url = r["url"]
                account_id = f"{site_name.lower()}:{username}"

                entities.append(
                    EntityOutput(
                        entity_type="account",
                        value=account_id,
                        attributes={
                            "site": site_name,
                            "url": profile_url,
                            "username": username,
                            "category": r["category"],
                            "verified": True,
                        },
                        confidence_score=0.9,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=username,
                        target_value=account_id,
                        relation_type="HAS_ACCOUNT",
                        attributes={"site": site_name, "admiralty": self.nato_admiralty},
                    )
                )

        raw_payload = {
            "target": username,
            "matches": confirmed_hits,
            "total_checked": len(TARGET_SITES),
            "total_found": len(confirmed_hits),
            "mock": False,
        }

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )
