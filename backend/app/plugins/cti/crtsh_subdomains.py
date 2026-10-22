from typing import Any, Dict, List, Optional, Set
import httpx
from app.config import is_mock_osint
from app.plugins.base import (
    BaseOSINTPlugin,
    EntityOutput,
    PluginCategory,
    PluginResult,
    RelationOutput,
)


class CrtshSubdomainsPlugin(BaseOSINTPlugin):
    """
    CTI crt.sh Certificate Transparency Subdomain Enumerator.
    Extraherar subdomäner och alternativa certifikatnamn via Certificate Transparency Logs.
    Helt passiv inhämtningsmetod som lämnar noll spår mot målets nätverksinfrastruktur.
    """

    plugin_id = "cti_crtsh"
    name = "crt.sh Certificate Transparency Enumerator"
    category = PluginCategory.CTI
    nato_admiralty = "A2"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Domain", "domain"]

    slug = "cti_crtsh"
    description = "Passiv certifikatsbaserad kartläggning av subdomäner och infrastruktur via crt.sh CT-loggar."
    version = "1.0.0"
    output_entities = ["domain", "certificate", "subdomain"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        domain = target.strip().lower().lstrip("www.")
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            mock_subdomains = [
                f"api.{domain}",
                f"vpn.{domain}",
                f"mail.{domain}",
                f"dev.{domain}",
                f"admin.{domain}",
            ]

            raw_payload: Dict[str, Any] = {
                "domain": domain,
                "subdomains": mock_subdomains,
                "total_found": len(mock_subdomains),
                "mock": True,
            }

            for sub in mock_subdomains:
                entities.append(
                    EntityOutput(
                        entity_type="domain",
                        value=sub,
                        attributes={"parent_domain": domain, "source": "crt.sh CT Log"},
                        confidence_score=0.95,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=domain,
                        target_value=sub,
                        relation_type="HAS_SUBDOMAIN",
                        attributes={"admiralty": self.nato_admiralty, "source": "crt.sh"},
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
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        raw_payload = {"domain": domain, "entries_count": 0, "mock": False}

        subdomains_set: Set[str] = set()
        try:
            resp = await opsec_client.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                entries = resp.json()
                raw_payload["entries_count"] = len(entries)
                for entry in entries:
                    name_value = entry.get("name_value", "")
                    for item in name_value.split("\n"):
                        clean_item = item.strip().lower().lstrip("*.")
                        if clean_item and clean_item.endswith(domain) and clean_item != domain:
                            subdomains_set.add(clean_item)

                for sub in sorted(subdomains_set):
                    entities.append(
                        EntityOutput(
                            entity_type="domain",
                            value=sub,
                            attributes={"parent_domain": domain, "source": "crt.sh"},
                            confidence_score=0.95,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=domain,
                            target_value=sub,
                            relation_type="HAS_SUBDOMAIN",
                            attributes={"admiralty": self.nato_admiralty},
                        )
                    )
                raw_payload["subdomains"] = sorted(list(subdomains_set))
        except Exception as e:
            raw_payload["error"] = str(e)

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )
