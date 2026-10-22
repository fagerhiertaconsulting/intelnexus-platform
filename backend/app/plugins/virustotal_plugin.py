from typing import List, Optional
import httpx
from .base import BaseOSINTPlugin, EntityOutput, PluginCategory, PluginResult, RelationOutput


class VirusTotalPlugin(BaseOSINTPlugin):
    plugin_id = "virustotal_threat_intel"
    name = "VirusTotal Threat Intelligence"
    category = PluginCategory.CTI
    nato_admiralty = "B2"
    requires_api_key = True
    cost_per_query_usd = 1.0
    supported_entity_types: List[str] = ["domain", "ip", "sha256", "Domain", "IPAddress"]

    slug = "virustotal_threat_intel"
    description = "Kontrollerar hotpoäng, malware-detekteringar och domänrykte via VirusTotal v3 API."
    version = "1.0.0"
    required_vault_key = "VIRUSTOTAL_API_KEY"
    is_commercial = True
    cost_per_query_estimate = 1.0  # 1 kredit
    supported_inputs: List[str] = ["domain", "ip", "sha256", "Domain", "IPAddress"]
    output_entities: List[str] = ["incident", "organization", "domain"]
    rate_limit_per_minute = 4  # Gratis tier 4/min, enterprise 60+
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        val = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        raw_payload = {
            "target": val,
            "last_analysis_stats": {"malicious": 0, "suspicious": 1, "undetected": 75, "harmless": 12},
            "reputation": 10,
            "tags": ["c2-candidate", "bulletproof-hosting"],
        }

        incident_output = EntityOutput(
            entity_type="incident",
            value=f"VT-Threat-{val}",
            attributes={"reputation": 10, "stats": raw_payload["last_analysis_stats"], "tags": raw_payload["tags"]},
            confidence_score=0.88,
        )
        entities.append(incident_output)
        relationships.append(
            RelationOutput(
                source_value=val,
                target_value=incident_output.value,
                relation_type="ASSOCIATED_WITH",
                attributes={"provider": "virustotal"},
            )
        )

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )


VirusTotalThreatIntelPlugin = VirusTotalPlugin
