import re
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


class RIPEstatASNProbePlugin(BaseOSINTPlugin):
    """
    CTI RIPEstat IP-to-ASN & Routing Probe.
    Hämtar BGP-routingdata, ASN, prefix-tillhörighet och operatörsinformation
    via officiella RIPE NCC RIPEstat API:er.
    """

    plugin_id = "cti_ripestat_asn"
    name = "RIPEstat BGP & ASN Intelligence Probe"
    category = PluginCategory.CTI
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["IPAddress", "IP", "ASN", "ipaddress", "ip", "asn"]

    slug = "cti_ripestat_asn"
    description = "Slår upp autonoma system (ASN), BGP-annonserade prefix och regionala RIR-tilldelningar via RIPEstat."
    version = "1.0.0"
    output_entities = ["asn", "prefix", "organization"]
    rate_limit_per_minute = 120
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        resource = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        is_asn = bool(re.match(r"^(AS)?\d+$", resource, re.IGNORECASE))
        asn_clean = resource.upper() if resource.upper().startswith("AS") else f"AS{resource}"

        if is_mock_osint():
            asn_num = asn_clean if is_asn else "AS13335"
            holder = "CLOUDFLARENET"
            prefix = "104.21.0.0/16" if not is_asn else "104.21.0.0/16"
            country = "US"

            raw_payload: Dict[str, Any] = {
                "resource": resource,
                "asn": asn_num,
                "holder": holder,
                "prefix": prefix,
                "country": country,
                "status": "routed",
                "rir": "RIPE NCC / ARIN",
                "mock": True,
            }

            asn_entity = EntityOutput(
                entity_type="AutonomousSystem",
                value=asn_num,
                attributes={"holder": holder, "country": country, "status": "routed"},
                confidence_score=1.0,
            )
            entities.append(asn_entity)

            prefix_entity = EntityOutput(
                entity_type="NetworkPrefix",
                value=prefix,
                attributes={"asn": asn_num, "rir": "ARIN"},
                confidence_score=1.0,
            )
            entities.append(prefix_entity)

            relationships.append(
                RelationOutput(
                    source_value=resource,
                    target_value=asn_num,
                    relation_type="ANNOUNCED_BY",
                    attributes={"admiralty": self.nato_admiralty, "holder": holder},
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=asn_num,
                    target_value=prefix,
                    relation_type="ROUTES_PREFIX",
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
        endpoint = "as-overview" if is_asn else "prefix-overview"
        url = f"https://stat.ripe.net/data/{endpoint}/data.json?resource={resource}"
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        raw_payload = {"resource": resource, "mock": False}

        try:
            resp = await opsec_client.get(url, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                raw_payload["ripe_data"] = data

                if is_asn:
                    holder_name = data.get("holder", "Unknown")
                    entities.append(
                        EntityOutput(
                            entity_type="AutonomousSystem",
                            value=asn_clean,
                            attributes={"holder": holder_name},
                            confidence_score=1.0,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=resource,
                            target_value=asn_clean,
                            relation_type="RESOLVES_TO_ASN",
                            attributes={"admiralty": self.nato_admiralty},
                        )
                    )
                else:
                    asns = data.get("asns", [])
                    for a in asns:
                        a_num = f"AS{a.get('asn')}"
                        a_holder = a.get("holder", "")
                        entities.append(
                            EntityOutput(
                                entity_type="AutonomousSystem",
                                value=a_num,
                                attributes={"holder": a_holder},
                                confidence_score=1.0,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=resource,
                                target_value=a_num,
                                relation_type="ANNOUNCED_BY",
                                attributes={"admiralty": self.nato_admiralty},
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
