import hashlib
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


class GravatarProbe(BaseOSINTPlugin):
    """
    SOCMINT Gravatar Profile Probe.
    Beräknar MD5 och SHA-256 av trimmad, lowercase e-postadress.
    Anropar https://en.gravatar.com/{hash}.json och extraherar namn, avatar-URL,
    PGP-nycklar och länkade konton vid träff.
    """

    plugin_id = "socmint_gravatar"
    name = "Gravatar Profile & Identity Probe"
    category = PluginCategory.SOCMINT
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Email", "EmailAddress", "email", "emailaddress"]

    slug = "socmint_gravatar"
    description = "Slår upp publika profiler, avatarer och länkade konton via Gravatar API baserat på e-posthash."
    version = "1.0.0"
    output_entities = ["person", "avatar", "account"]
    rate_limit_per_minute = 100
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        email = target.strip().lower()
        email_md5 = hashlib.md5(email.encode("utf-8"), usedforsecurity=False).hexdigest()  # nosec B324
        email_sha256 = hashlib.sha256(email.encode("utf-8")).hexdigest()

        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            display_name = email.split("@")[0].replace(".", " ").title()
            avatar_url = f"https://secure.gravatar.com/avatar/{email_md5}?s=400"
            profile_url = f"https://gravatar.com/{email_md5}"

            raw_payload: Dict[str, Any] = {
                "hash_md5": email_md5,
                "hash_sha256": email_sha256,
                "entry": [
                    {
                        "id": email_md5,
                        "hash": email_md5,
                        "requestHash": email_md5,
                        "profileUrl": profile_url,
                        "preferredUsername": email.split("@")[0],
                        "thumbnailUrl": avatar_url,
                        "displayName": display_name,
                        "aboutMe": "Verified OSINT profile test subject",
                        "currentLocation": "Stockholm, Sweden",
                        "accounts": [
                            {
                                "domain": "github.com",
                                "display": "github",
                                "url": f"https://github.com/{email.split('@')[0]}",
                            },
                            {
                                "domain": "twitter.com",
                                "display": "twitter",
                                "url": f"https://twitter.com/{email.split('@')[0]}",
                            },
                        ],
                    }
                ],
                "mock": True,
            }

            entities.append(
                EntityOutput(
                    entity_type="Person",
                    value=display_name,
                    attributes={
                        "display_name": display_name,
                        "location": "Stockholm, Sweden",
                        "gravatar_profile": profile_url,
                    },
                    confidence_score=1.0,
                )
            )
            entities.append(
                EntityOutput(
                    entity_type="Avatar",
                    value=avatar_url,
                    attributes={"source": "Gravatar", "hash_md5": email_md5},
                    confidence_score=1.0,
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=email,
                    target_value=display_name,
                    relation_type="IDENTIFIED_AS",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=email,
                    target_value=avatar_url,
                    relation_type="HAS_AVATAR",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )

            for acc in raw_payload["entry"][0]["accounts"]:
                acc_val = acc["url"]
                entities.append(
                    EntityOutput(
                        entity_type="account",
                        value=acc_val,
                        attributes={"domain": acc["domain"], "display": acc["display"]},
                        confidence_score=0.95,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=display_name,
                        target_value=acc_val,
                        relation_type="LINKED_ACCOUNT",
                        attributes={"domain": acc["domain"]},
                    )
                )

            return PluginResult(
                entities=entities,
                relationships=relationships,
                raw_payload=raw_payload,
                nato_admiralty=self.nato_admiralty,
                cost_usd=self.cost_per_query_usd,
            )

        # Skarpt läge
        url = f"https://en.gravatar.com/{email_md5}.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IntelNexus/1.0",
            "Accept": "application/json",
        }
        raw_payload = {"hash_md5": email_md5, "hash_sha256": email_sha256, "status": "not_found", "mock": False}

        try:
            resp = await opsec_client.get(url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_payload = data
                raw_payload["mock"] = False
                entries = data.get("entry", [])
                if entries:
                    entry = entries[0]
                    display_name = entry.get("displayName") or entry.get("preferredUsername") or email
                    avatar_url = entry.get("thumbnailUrl") or f"https://secure.gravatar.com/avatar/{email_md5}"

                    entities.append(
                        EntityOutput(
                            entity_type="Person",
                            value=display_name,
                            attributes={
                                "display_name": display_name,
                                "location": entry.get("currentLocation", ""),
                                "about": entry.get("aboutMe", ""),
                            },
                            confidence_score=1.0,
                        )
                    )
                    entities.append(
                        EntityOutput(
                            entity_type="Avatar",
                            value=avatar_url,
                            attributes={"source": "Gravatar", "hash_md5": email_md5},
                            confidence_score=1.0,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=email,
                            target_value=display_name,
                            relation_type="IDENTIFIED_AS",
                            attributes={"admiralty": self.nato_admiralty},
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=email,
                            target_value=avatar_url,
                            relation_type="HAS_AVATAR",
                            attributes={"admiralty": self.nato_admiralty},
                        )
                    )

                    for acc in entry.get("accounts", []):
                        acc_url = acc.get("url")
                        if acc_url:
                            entities.append(
                                EntityOutput(
                                    entity_type="account",
                                    value=acc_url,
                                    attributes={"domain": acc.get("domain", ""), "display": acc.get("display", "")},
                                    confidence_score=0.95,
                                )
                            )
                            relationships.append(
                                RelationOutput(
                                    source_value=display_name,
                                    target_value=acc_url,
                                    relation_type="LINKED_ACCOUNT",
                                    attributes={"domain": acc.get("domain", "")},
                                )
                            )
        except Exception as e:
            raw_payload["error"] = str(e)

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )
