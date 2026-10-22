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


class OpenCorporatesPlugin(BaseOSINTPlugin):
    """
    FINMINT OpenCorporates Global Company Intelligence.
    Global bolagssökning via OpenCorporates API.
    Extraherar bolagsform, styrelseledamöter, filialer och jurisdiktion.
    """

    plugin_id = "finmint_opencorporates"
    name = "OpenCorporates Global Corporate Intelligence"
    category = PluginCategory.FINMINT
    nato_admiralty = "B2"
    requires_api_key = True
    cost_per_query_usd = 0.0  # Offentlig sökning är gratis, kommersiell tier via nyckel
    supported_entity_types = ["Company", "Organization", "company", "organization"]

    slug = "finmint_opencorporates"
    description = "Global bolagssökning och ledningskartläggning över mer än 200 miljoner bolag och jurisdiktioner."
    version = "1.0.0"
    required_vault_key = "OPENCORPORATES_API_KEY"
    output_entities = ["company", "person", "jurisdiction"]
    rate_limit_per_minute = 30
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        company_query = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            company_number = "08942119"
            jurisdiction = "gb"
            company_name = company_query if company_query else "Acme Global Solutions Ltd"
            officers = [
                {"name": "Sarah Connor", "role": "Director", "appointed_on": "2018-05-10"},
                {"name": "James Alexander", "role": "Secretary", "appointed_on": "2019-01-20"},
            ]

            raw_payload: Dict[str, Any] = {
                "target": company_query,
                "company": {
                    "name": company_name,
                    "company_number": company_number,
                    "jurisdiction_code": jurisdiction,
                    "incorporation_date": "2014-03-15",
                    "company_type": "Private Limited Company",
                    "current_status": "Active",
                    "registry_url": f"https://opencorporates.com/companies/{jurisdiction}/{company_number}",
                    "officers": officers,
                },
                "mock": True,
            }

            comp_entity = EntityOutput(
                entity_type="Company",
                value=company_name,
                attributes={
                    "company_number": company_number,
                    "jurisdiction": jurisdiction,
                    "status": "Active",
                    "incorporation_date": "2014-03-15",
                    "type": "Private Limited Company",
                },
                confidence_score=0.9,
            )
            entities.append(comp_entity)

            jur_entity = EntityOutput(
                entity_type="Jurisdiction",
                value=jurisdiction.upper(),
                attributes={"country_code": jurisdiction.upper()},
                confidence_score=1.0,
            )
            entities.append(jur_entity)

            relationships.append(
                RelationOutput(
                    source_value=company_name,
                    target_value=jurisdiction.upper(),
                    relation_type="INCORPORATED_IN",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )

            for off in officers:
                officer_name = off["name"]
                entities.append(
                    EntityOutput(
                        entity_type="Person",
                        value=officer_name,
                        attributes={"role": off["role"], "company": company_name},
                        confidence_score=0.85,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=officer_name,
                        target_value=company_name,
                        relation_type="OFFICER_OF",
                        attributes={"role": off["role"], "appointed": off["appointed_on"]},
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
        params: Dict[str, Any] = {"q": company_query}
        if api_key:
            params["api_token"] = api_key
        url = "https://api.opencorporates.com/v0.4/companies/search"

        raw_payload = {"target": company_query, "results": [], "mock": False}
        try:
            resp = await opsec_client.get(url, params=params, timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", {}).get("companies", [])
                raw_payload["results"] = results
                for item in results[:3]:
                    c = item.get("company", {})
                    c_name = c.get("name", "")
                    c_num = c.get("company_number", "")
                    c_jur = c.get("jurisdiction_code", "")

                    if c_name:
                        entities.append(
                            EntityOutput(
                                entity_type="Company",
                                value=c_name,
                                attributes={"company_number": c_num, "jurisdiction": c_jur},
                                confidence_score=0.9,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=company_query,
                                target_value=c_name,
                                relation_type="IDENTIFIED_AS",
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
