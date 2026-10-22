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


class ShodanCTIPlugin(BaseOSINTPlugin):
    """
    CTI Shodan Threat Intelligence & Attack Surface Analyzer.
    REST-integration med Shodan Host API för identifiering av öppna portar,
    protokollbanners, OS-fingeravtryck och kända CVE-sårbarheter.
    FinOps: Kontrollerar query-krediter via Redis Token Bucket innan anrop utförs.
    """

    plugin_id = "cti_shodan"
    name = "Shodan CTI Attack Surface Intelligence"
    category = PluginCategory.CTI
    nato_admiralty = "B2"
    requires_api_key = True
    cost_per_query_usd = 1.0  # 1 kredit per query
    supported_entity_types = ["IPAddress", "IP", "ipaddress", "ip"]

    slug = "cti_shodan"
    description = "Djupgående attackytkartläggning, portskanning och CVE-detektering via Shodan API."
    version = "1.0.0"
    required_vault_key = "SHODAN_API_KEY"
    is_commercial = True
    cost_per_query_estimate = 1.0
    output_entities = ["organization", "domain", "port", "vulnerability"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        from app.core.finops.rate_limiter import rate_limiter

        ip = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        # FinOps: Kontrollera query-kredit via Token Bucket
        credit_acquired = rate_limiter.acquire(
            key="shodan_query_credit",
            cost=1,
            max_tokens=100,
            refill_rate_per_sec=0.1,
        )

        if not credit_acquired and not is_mock_osint():
            return PluginResult(
                entities=[],
                relationships=[],
                raw_payload={"error": "FinOps: Shodan query credit limit reached.", "quota_exceeded": True},
                nato_admiralty=self.nato_admiralty,
                cost_usd=0.0,
            )

        if is_mock_osint():
            org_name = "Cloudflare Inc."
            ports = [80, 443, 8080, 8443]
            hostname = f"host-{ip.replace('.', '-')}.cloudflare.net"
            vulns = ["CVE-2023-44487", "CVE-2024-21626"]

            raw_payload: Dict[str, Any] = {
                "ip_str": ip,
                "org": org_name,
                "isp": "Cloudflare",
                "country_code": "US",
                "os": "Linux",
                "ports": ports,
                "hostnames": [hostname],
                "vulns": vulns,
                "finops_credit_deducted": 1,
                "mock": True,
            }

            entities.append(
                EntityOutput(
                    entity_type="Organization",
                    value=org_name,
                    attributes={"isp": "Cloudflare", "country": "US"},
                    confidence_score=0.95,
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=ip,
                    target_value=org_name,
                    relation_type="OPERATES_ON",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )

            entities.append(
                EntityOutput(
                    entity_type="Domain",
                    value=hostname,
                    attributes={"ports": ports},
                    confidence_score=0.9,
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=ip,
                    target_value=hostname,
                    relation_type="RESOLVES_TO",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )

            for v in vulns:
                entities.append(
                    EntityOutput(
                        entity_type="Vulnerability",
                        value=v,
                        attributes={"severity": "High", "ip": ip},
                        confidence_score=0.85,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=ip,
                        target_value=v,
                        relation_type="AFFECTED_BY",
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
        url = f"https://api.shodan.io/shodan/host/{ip}"
        params = {"key": api_key or ""}
        raw_payload = {"ip_str": ip, "mock": False}

        try:
            resp = await opsec_client.get(url, params=params, timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_payload = data
                org_val = data.get("org", "Unknown")
                entities.append(
                    EntityOutput(
                        entity_type="Organization",
                        value=org_val,
                        attributes={"isp": data.get("isp", "")},
                        confidence_score=0.95,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=ip,
                        target_value=org_val,
                        relation_type="OPERATES_ON",
                        attributes={"admiralty": self.nato_admiralty},
                    )
                )
            else:
                raw_payload["status_code"] = resp.status_code
        except Exception as e:
            raw_payload["error"] = str(e)

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )
