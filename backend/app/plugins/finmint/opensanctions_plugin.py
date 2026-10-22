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


class OpenSanctionsPlugin(BaseOSINTPlugin):
    """
    FINMINT OpenSanctions PEP & Sanctions Screening.
    Kontroll mot OpenSanctions REST API för PEP (politically exposed persons),
    internationella sanktionslistor (OFAC, EU, UN, UK) och efterlysningar.
    """

    plugin_id = "finmint_opensanctions"
    name = "OpenSanctions Screening Engine"
    category = PluginCategory.FINMINT
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Person", "Company", "Organization", "person", "company", "organization"]

    slug = "finmint_opensanctions"
    description = "Söker mot globala sanktionslistor, PEP-databaser och brottsregister via OpenSanctions."
    version = "1.0.0"
    output_entities = ["sanction", "pep", "person", "company"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        search_target = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            is_sanctioned_mock = "sanction" in search_target.lower() or "target" in search_target.lower()
            matched_datasets = ["us_ofac_sdn", "eu_fsf", "un_sc_sanctions"] if is_sanctioned_mock else []

            raw_payload: Dict[str, Any] = {
                "query": search_target,
                "total_matches": 1 if is_sanctioned_mock else 0,
                "results": [
                    {
                        "id": f"os-{abs(hash(search_target)) % 100000}",
                        "caption": search_target,
                        "schema": "Person",
                        "score": 0.95,
                        "datasets": matched_datasets,
                        "topics": ["sanction", "pep"],
                        "programs": ["RUSSIA-EO14024", "GLOBAL-MAGNITSKY"],
                        "first_seen": "2022-03-01T00:00:00Z",
                    }
                ]
                if is_sanctioned_mock
                else [],
                "mock": True,
            }

            if is_sanctioned_mock:
                sanction_node = EntityOutput(
                    entity_type="SanctionListing",
                    value=f"Sanction:{search_target}",
                    attributes={
                        "score": 0.95,
                        "datasets": matched_datasets,
                        "topics": ["sanction", "pep"],
                        "programs": ["RUSSIA-EO14024", "GLOBAL-MAGNITSKY"],
                    },
                    confidence_score=0.95,
                )
                entities.append(sanction_node)

                relationships.append(
                    RelationOutput(
                        source_value=search_target,
                        target_value=sanction_node.value,
                        relation_type="LISTED_UNDER_SANCTIONS",
                        attributes={"admiralty": self.nato_admiralty, "score": 0.95},
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
        url = "https://api.opensanctions.org/search/default"
        params = {"q": search_target, "limit": "5"}
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"

        raw_payload = {"query": search_target, "results": [], "mock": False}
        try:
            resp = await opsec_client.get(url, params=params, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                raw_payload["results"] = results
                for r in results:
                    caption = r.get("caption", search_target)
                    datasets = r.get("datasets", [])
                    score = r.get("score", 1.0)
                    topics = r.get("properties", {}).get("topics", [])

                    node_id = f"Sanction:{caption}"
                    entities.append(
                        EntityOutput(
                            entity_type="SanctionListing",
                            value=node_id,
                            attributes={"score": score, "datasets": datasets, "topics": topics},
                            confidence_score=float(score) if isinstance(score, (int, float)) else 0.9,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=search_target,
                            target_value=node_id,
                            relation_type="LISTED_UNDER_SANCTIONS",
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
