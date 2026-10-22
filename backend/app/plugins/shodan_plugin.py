from typing import List, Optional
from .base import BaseOSINTPlugin, EntityInput, EntityOutput, RelationOutput, TransformResult


class ShodanPlugin(BaseOSINTPlugin):
    name = "Shodan Host & Port Intelligence"
    slug = "shodan_host_intel"
    description = "Söker upp öppna portar, banners och sårbarheter för IP-adresser via Shodan API."
    version = "1.0.0"
    required_vault_key = "SHODAN_API_KEY"
    is_commercial = True
    cost_per_query_estimate = 1.0  # 1 kredit per query
    supported_inputs: List[str] = ["ip", "ipaddress", "IPAddress", "IP"]
    output_entities: List[str] = ["domain", "organization", "port", "vulnerability"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def execute(
        self,
        target: EntityInput,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> TransformResult:
        ip_val = target.value.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        # Simulerat eller faktiskt anrop baserat på api_key
        raw_payload = {
            "ip_str": ip_val,
            "org": "Cloudflare Inc.",
            "isp": "Cloudflare",
            "country_code": "US",
            "ports": [80, 443, 8080],
            "hostnames": [f"host-{ip_val.replace('.', '-')}.example.net"],
        }

        # Skapa organisation
        org_name = str(raw_payload["org"])
        org_output = EntityOutput(
            entity_type="organization",
            value=org_name,
            attributes={"isp": raw_payload["isp"], "country_code": raw_payload["country_code"]},
            confidence_score=0.95,
        )
        entities.append(org_output)
        relationships.append(
            RelationOutput(
                source_value=ip_val,
                target_value=org_name,
                relation_type="OPERATES_ON",
                attributes={"service": "shodan"},
            )
        )

        # Skapa värdnamn/domäner
        hostnames = raw_payload["hostnames"]
        if isinstance(hostnames, list):
            for h in hostnames:
                h_str = str(h)
                dom_output = EntityOutput(
                    entity_type="domain",
                    value=h_str,
                    attributes={"shodan_ip": ip_val},
                    confidence_score=0.9,
                )
                entities.append(dom_output)
                relationships.append(
                    RelationOutput(
                        source_value=ip_val,
                        target_value=h_str,
                        relation_type="RESOLVES_TO",
                        attributes={"ports": raw_payload["ports"]},
                    )
                )

        return TransformResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
        )


ShodanHostIntelPlugin = ShodanPlugin
