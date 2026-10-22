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


class HIBPBreachProbe(BaseOSINTPlugin):
    """
    DARKINT HaveIBeenPwned Breach & Password Intelligence Probe.
    Utför integritetsskyddad analys av dataläckor och komprometterade lösenord:
    - Pwned Passwords via k-anonymitetsmodellen (endast 5-teckens SHA-1-prefix överförs).
    - E-postläckagekontroll via HaveIBeenPwned v3 API (stöd för API-nyckel via valvet).
    """

    plugin_id = "darkint_hibp_breach"
    name = "HaveIBeenPwned Breach & Password Intelligence"
    category = PluginCategory.DARKINT
    nato_admiralty = "A1"
    requires_api_key = False  # Lösenords-k-anonymitet är gratis; e-post API kan använda nyckel
    cost_per_query_usd = 0.0
    supported_entity_types = [
        "Email",
        "EmailAddress",
        "Password",
        "PasswordHash",
        "email",
        "password",
    ]

    slug = "darkint_hibp_breach"
    description = "Identifierar komprometterade konton och lösenordsläckor via HIBP och k-anonymitet."
    version = "1.0.0"
    required_vault_key = "HIBP_API_KEY"
    output_entities = ["databreach", "compromised_credential", "email"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        query_val = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        import re

        is_email = bool(re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z0-9-]{2,}$", query_val))

        if is_mock_osint():
            if is_email:
                breaches = [
                    {
                        "name": "Adobe",
                        "title": "Adobe Systems",
                        "domain": "adobe.com",
                        "breach_date": "2013-10-04",
                        "pwn_count": 152445165,
                        "data_classes": ["Email addresses", "Password hints", "Passwords", "Usernames"],
                    },
                    {
                        "name": "LinkedIn",
                        "title": "LinkedIn",
                        "domain": "linkedin.com",
                        "breach_date": "2016-05-17",
                        "pwn_count": 164611595,
                        "data_classes": ["Email addresses", "Passwords"],
                    },
                    {
                        "name": "Canva",
                        "title": "Canva",
                        "domain": "canva.com",
                        "breach_date": "2019-05-24",
                        "pwn_count": 137000000,
                        "data_classes": ["Email addresses", "Names", "Passwords", "Usernames"],
                    },
                ]

                raw_payload: Dict[str, Any] = {
                    "account": query_val,
                    "breaches": breaches,
                    "breach_count": len(breaches),
                    "mock": True,
                }

                for b in breaches:
                    breach_node = EntityOutput(
                        entity_type="DataBreach",
                        value=f"Breach:{b['name']}",
                        attributes={
                            "title": b["title"],
                            "domain": b["domain"],
                            "breach_date": b["breach_date"],
                            "data_classes": b["data_classes"],
                            "pwn_count": b["pwn_count"],
                        },
                        confidence_score=1.0,
                    )
                    entities.append(breach_node)

                    relationships.append(
                        RelationOutput(
                            source_value=query_val,
                            target_value=breach_node.value,
                            relation_type="EXPOSED_IN",
                            attributes={"admiralty": self.nato_admiralty, "breach_date": b["breach_date"]},
                        )
                    )
            else:
                # Mock för lösenords-k-anonymitet
                sha1_hash = hashlib.sha1(query_val.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
                prefix = sha1_hash[:5]
                suffix = sha1_hash[5:]

                raw_payload = {
                    "sha1_prefix": prefix,
                    "sha1_suffix_hash": f"{suffix[:4]}****",
                    "pwned_count": 42718,
                    "k_anonymity_enforced": True,
                    "mock": True,
                }

                cred_node = EntityOutput(
                    entity_type="CompromisedCredential",
                    value=f"PwnedPassword:{prefix}",
                    attributes={"pwn_count": 42718, "k_anonymity": True},
                    confidence_score=1.0,
                )
                entities.append(cred_node)
                relationships.append(
                    RelationOutput(
                        source_value=query_val,
                        target_value=cred_node.value,
                        relation_type="KNOWN_LEAKED_PASSWORD",
                        attributes={"admiralty": self.nato_admiralty},
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
        if is_email:
            headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
            if api_key:
                headers["hibp-api-key"] = api_key
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{query_val}?truncateResponse=false"
            raw_payload = {"account": query_val, "mock": False}

            try:
                resp = await opsec_client.get(url, headers=headers, timeout=6.0)
                if resp.status_code == 200:
                    breach_list = resp.json()
                    raw_payload["breaches"] = breach_list
                    for b in breach_list:
                        b_name = b.get("Name", "Unknown")
                        entities.append(
                            EntityOutput(
                                entity_type="DataBreach",
                                value=f"Breach:{b_name}",
                                attributes={
                                    "title": b.get("Title"),
                                    "domain": b.get("Domain"),
                                    "breach_date": b.get("BreachDate"),
                                },
                                confidence_score=1.0,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=query_val,
                                target_value=f"Breach:{b_name}",
                                relation_type="EXPOSED_IN",
                                attributes={"admiralty": self.nato_admiralty},
                            )
                        )
                elif resp.status_code == 404:
                    raw_payload["breaches"] = []
            except Exception as e:
                raw_payload["error"] = str(e)
        else:
            # k-anonymitet för lösenord
            sha1_full = hashlib.sha1(query_val.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
            prefix = sha1_full[:5]
            suffix = sha1_full[5:]
            url = f"https://api.pwnedpasswords.com/range/{prefix}"
            headers = {"User-Agent": "IntelNexus-OSINT/1.0"}
            raw_payload = {"sha1_prefix": prefix, "k_anonymity": True, "mock": False}

            try:
                resp = await opsec_client.get(url, headers=headers, timeout=5.0)
                if resp.status_code == 200:
                    pwned_count = 0
                    for line in resp.text.splitlines():
                        if ":" in line:
                            s_hash, count = line.strip().split(":", 1)
                            if s_hash.upper() == suffix:
                                pwned_count = int(count)
                                break
                    raw_payload["pwned_count"] = pwned_count
                    if pwned_count > 0:
                        cred_node = EntityOutput(
                            entity_type="CompromisedCredential",
                            value=f"PwnedPassword:{prefix}",
                            attributes={"pwn_count": pwned_count, "k_anonymity": True},
                            confidence_score=1.0,
                        )
                        entities.append(cred_node)
                        relationships.append(
                            RelationOutput(
                                source_value=query_val,
                                target_value=cred_node.value,
                                relation_type="KNOWN_LEAKED_PASSWORD",
                                attributes={"admiralty": self.nato_admiralty, "pwn_count": pwned_count},
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
