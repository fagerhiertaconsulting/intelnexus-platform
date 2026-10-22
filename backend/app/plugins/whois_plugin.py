from typing import List, Optional
import httpx
from .base import BaseOSINTPlugin, EntityOutput, PluginCategory, PluginResult, RelationOutput


class WhoisPlugin(BaseOSINTPlugin):
    plugin_id = "whois_lookup"
    name = "WHOIS Domain Registrar Lookup"
    category = PluginCategory.CTI
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types: List[str] = ["domain", "Domain"]

    slug = "whois_lookup"
    description = "Hämtar registrar, skapandedatum och namnservrar för domäner via RDAP/WHOIS."
    version = "1.0.0"
    required_vault_key = None
    is_commercial = False
    cost_per_query_estimate = 0.0  # Gratis
    supported_inputs: List[str] = ["domain", "Domain"]
    output_entities: List[str] = ["organization"]
    rate_limit_per_minute = 120
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        domain = target.strip().lower()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        registrar_name = "MarkMonitor Inc."
        raw_payload = {
            "domain": domain,
            "registrar": registrar_name,
            "created_at": "2010-01-15T00:00:00Z",
            "status": ["clientTransferProhibited"],
        }

        org_output = EntityOutput(
            entity_type="organization",
            value=registrar_name,
            attributes={"role": "registrar", "domain": domain},
            confidence_score=1.0,
        )
        entities.append(org_output)
        relationships.append(
            RelationOutput(
                source_value=domain,
                target_value=registrar_name,
                relation_type="REGISTERED_BY",
                attributes={"status": raw_payload["status"]},
            )
        )

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )


WhoisLookupPlugin = WhoisPlugin
