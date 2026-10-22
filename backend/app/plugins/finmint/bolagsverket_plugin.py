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


class BolagsverketPlugin(BaseOSINTPlugin):
    """
    FINMINT Bolagsverket Swedish Company Registry Plugin.
    Uppslag mot Bolagsverkets öppna datagränssnitt / API för organisationsnummer och företagsnamn.
    Officiell myndighetskälla för svenska aktiebolag och juridiska personer.
    """

    plugin_id = "finmint_bolagsverket"
    name = "Bolagsverket Swedish Company Registry"
    category = PluginCategory.FINMINT
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Company", "Organization", "OrgNumber", "company", "organization"]

    slug = "finmint_bolagsverket"
    description = (
        "Officiellt registeruppslag för svenska bolag, organisationsnummer, säte och bolagsform via Bolagsverket."
    )
    version = "1.0.0"
    output_entities = ["company", "location", "organization"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        query = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        # Rensa och validera organisationsnummer (10 siffror, t.ex. 559400-0000 eller 5594000000)
        is_org_nr = bool(re.match(r"^\d{6}-?\d{4}$", query))
        normalized_org = re.sub(r"\D", "", query) if is_org_nr else "5594000000"

        if is_mock_osint():
            company_name = query if not is_org_nr else "Fagerhierta Consulting AB"
            display_org = f"{normalized_org[:6]}-{normalized_org[6:]}" if len(normalized_org) == 10 else "559400-0000"

            raw_payload: Dict[str, Any] = {
                "organisationsnummer": display_org,
                "foretagsnamn": company_name,
                "organisationsform": "Aktiebolag (AB)",
                "status": "Aktivt / Registrerat",
                "registreringsdatum": "2022-01-15",
                "juridiskt_sate": "Stockholm",
                "postadress": "Kungsgatan 1, 111 43 Stockholm",
                "sni_kod": "62020",
                "sni_beskrivning": "Datakonsultverksamhet",
                "mock": True,
            }

            company_entity = EntityOutput(
                entity_type="Company",
                value=company_name,
                attributes={
                    "organisationsnummer": display_org,
                    "bolagsform": raw_payload["organisationsform"],
                    "status": raw_payload["status"],
                    "sate": raw_payload["juridiskt_sate"],
                    "registreringsdatum": raw_payload["registreringsdatum"],
                    "sni": f"{raw_payload['sni_kod']} - {raw_payload['sni_beskrivning']}",
                },
                confidence_score=1.0,
            )
            entities.append(company_entity)

            location_entity = EntityOutput(
                entity_type="Location",
                value=raw_payload["juridiskt_sate"],
                attributes={"adress": raw_payload["postadress"], "land": "Sverige"},
                confidence_score=1.0,
            )
            entities.append(location_entity)

            relationships.append(
                RelationOutput(
                    source_value=query,
                    target_value=company_name,
                    relation_type="RESOLVES_TO_COMPANY",
                    attributes={"organisationsnummer": display_org, "admiralty": self.nato_admiralty},
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=company_name,
                    target_value=raw_payload["juridiskt_sate"],
                    relation_type="LOCATED_IN",
                    attributes={"type": "juridiskt_sate"},
                )
            )

            return PluginResult(
                entities=entities,
                relationships=relationships,
                raw_payload=raw_payload,
                nato_admiralty=self.nato_admiralty,
                cost_usd=self.cost_per_query_usd,
            )

        # Skarpt läge: anropa Bolagsverkets öppna datagränssnitt / offentliga sökgränssnitt
        url = (
            f"https://api.bolagsverket.se/oppnadata/v1/foretag/{normalized_org}"
            if is_org_nr
            else f"https://api.bolagsverket.se/oppnadata/v1/foretag/sok?namn={query}"
        )
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        raw_payload = {"target": query, "status": "query_completed", "mock": False}

        try:
            resp = await opsec_client.get(url, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_payload["bolagsverket_data"] = data
                comp_name = data.get("foretagsnamn", query)
                org_nr = data.get("organisationsnummer", normalized_org)

                entities.append(
                    EntityOutput(
                        entity_type="Company",
                        value=comp_name,
                        attributes={"org_nr": org_nr, "form": data.get("organisationsform", "AB")},
                        confidence_score=1.0,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=query,
                        target_value=comp_name,
                        relation_type="RESOLVES_TO_COMPANY",
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
