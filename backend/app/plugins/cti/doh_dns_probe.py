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


class DoHDNSProbePlugin(BaseOSINTPlugin):
    """
    CTI DNS-over-HTTPS (DoH) Resolver Plugin via Cloudflare 1.1.1.1.
    Utför deterministisk och integritetsskyddad upplösning av A, AAAA, MX, TXT och SOA-poster
    utan att exponera förfrågningar för lokala DNS-lyssnare eller ISP-loggning.
    """

    plugin_id = "cti_doh_dns"
    name = "DNS-over-HTTPS (DoH) Security Resolver"
    category = PluginCategory.CTI
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Domain", "domain", "Hostname", "hostname"]

    slug = "cti_doh_dns"
    description = "Krypterad DNS-uppslagning av infrastrukturposter (A, AAAA, MX, TXT, SOA) via Cloudflare DoH API."
    version = "1.0.0"
    output_entities = ["ip", "mailserver", "dnsrecord"]
    rate_limit_per_minute = 180
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

        record_types = ["A", "AAAA", "MX", "TXT", "SOA"]

        if is_mock_osint():
            mock_records: Dict[str, List[str]] = {
                "A": ["104.21.55.12", "172.67.180.44"],
                "AAAA": ["2606:4700:3031::6815:370c"],
                "MX": [f"mail.{domain}", "alt1.aspmx.l.google.com"],
                "TXT": ["v=spf1 include:_spf.google.com ~all"],
                "SOA": ["ns1.cloudflare.com"],
            }

            raw_payload: Dict[str, Any] = {
                "domain": domain,
                "dns_records": mock_records,
                "resolver": "1.1.1.1 (Cloudflare DoH)",
                "mock": True,
            }

            # A- och AAAA-poster -> IPAddress noder
            for ip in mock_records["A"] + mock_records["AAAA"]:
                entities.append(
                    EntityOutput(
                        entity_type="IPAddress",
                        value=ip,
                        attributes={"domain": domain, "dns_type": "A/AAAA"},
                        confidence_score=1.0,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=domain,
                        target_value=ip,
                        relation_type="RESOLVES_TO",
                        attributes={"admiralty": self.nato_admiralty},
                    )
                )

            # MX -> MailServer noder
            for mx in mock_records["MX"]:
                entities.append(
                    EntityOutput(
                        entity_type="MailServer",
                        value=mx,
                        attributes={"priority": 10, "domain": domain},
                        confidence_score=1.0,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=domain,
                        target_value=mx,
                        relation_type="HAS_MAIL_SERVER",
                        attributes={"admiralty": self.nato_admiralty},
                    )
                )

            # TXT & SOA -> DNSRecord
            for r_type in ["TXT", "SOA"]:
                for val in mock_records[r_type]:
                    record_id = f"{r_type}:{val[:30]}"
                    entities.append(
                        EntityOutput(
                            entity_type="DNSRecord",
                            value=record_id,
                            attributes={"type": r_type, "value": val},
                            confidence_score=1.0,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=domain,
                            target_value=record_id,
                            relation_type="HAS_DNS_RECORD",
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
        headers = {"Accept": "application/dns-json", "User-Agent": "IntelNexus-OSINT/1.0"}
        raw_payload = {"domain": domain, "records": {}, "mock": False}

        async def fetch_record(r_type: str) -> Dict[str, Any]:
            url = f"https://1.1.1.1/dns-query?name={domain}&type={r_type}"
            try:
                resp = await opsec_client.get(url, headers=headers, timeout=5.0)
                if resp.status_code == 200:
                    return {r_type: resp.json().get("Answer", [])}
            except Exception:
                pass
            return {r_type: []}

        tasks = [fetch_record(t) for t in record_types]
        results = await asyncio.gather(*tasks)

        for res in results:
            for r_type, answers in res.items():
                raw_payload["records"][r_type] = answers
                for ans in answers:
                    data_val = ans.get("data", "")
                    if not data_val:
                        continue
                    if r_type in ("A", "AAAA"):
                        entities.append(
                            EntityOutput(
                                entity_type="IPAddress",
                                value=data_val,
                                attributes={"type": r_type, "ttl": ans.get("TTL", 300)},
                                confidence_score=1.0,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=domain,
                                target_value=data_val,
                                relation_type="RESOLVES_TO",
                                attributes={"admiralty": self.nato_admiralty},
                            )
                        )
                    elif r_type == "MX":
                        mx_host = data_val.split()[-1].rstrip(".")
                        entities.append(
                            EntityOutput(
                                entity_type="MailServer",
                                value=mx_host,
                                attributes={"raw": data_val},
                                confidence_score=1.0,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=domain,
                                target_value=mx_host,
                                relation_type="HAS_MAIL_SERVER",
                                attributes={"admiralty": self.nato_admiralty},
                            )
                        )
                    else:
                        rec_id = f"{r_type}:{data_val[:30]}"
                        entities.append(
                            EntityOutput(
                                entity_type="DNSRecord",
                                value=rec_id,
                                attributes={"type": r_type, "data": data_val},
                                confidence_score=1.0,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=domain,
                                target_value=rec_id,
                                relation_type="HAS_DNS_RECORD",
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
