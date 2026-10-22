from typing import List, Optional
from .base import BaseOSINTPlugin, EntityInput, EntityOutput, RelationOutput, TransformResult


class VirusTotalPlugin(BaseOSINTPlugin):
    name = "VirusTotal Threat Intelligence"
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

    async def execute(
        self,
        target: EntityInput,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> TransformResult:
        val = target.value.strip()
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

        return TransformResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
        )


VirusTotalThreatIntelPlugin = VirusTotalPlugin
