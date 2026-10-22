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


class OverpassInfraPlugin(BaseOSINTPlugin):
    """
    GEOINT OpenStreetMap Overpass Spatial Infrastructure Intelligence.
    Kör Overpass API-frågor mot OpenStreetMap för identifiering av kritisk spatial
    infrastruktur såsom telekommaster, mobilmaster, kraftledningar, ställverk och transportnav.
    """

    plugin_id = "geoint_overpass_infra"
    name = "OpenStreetMap Overpass Infrastructure Intelligence"
    category = PluginCategory.GEOINT
    nato_admiralty = "B2"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = [
        "Coordinates",
        "BoundingBox",
        "Location",
        "Infrastructure",
        "coordinates",
        "boundingbox",
        "location",
    ]

    slug = "geoint_overpass_infra"
    description = "Spatial kartläggning av telekommaster, kraftnät och transportinfrastruktur via OSM Overpass API."
    version = "1.0.0"
    output_entities = ["infrastructure", "telecom_mast", "power_line", "location"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        query_str = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        # Extrahera lat, lon
        lat, lon = 59.3293, 18.0686
        match = re.search(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", query_str)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
            except ValueError:
                pass

        if is_mock_osint():
            mock_elements = [
                {
                    "type": "node",
                    "id": 101234567,
                    "lat": lat + 0.005,
                    "lon": lon + 0.008,
                    "tags": {
                        "man_made": "mast",
                        "tower:type": "communication",
                        "operator": "Telia / Ericsson",
                        "height": "48",
                        "description": "5G Telecom Base Station",
                    },
                },
                {
                    "type": "way",
                    "id": 209876543,
                    "tags": {
                        "power": "line",
                        "voltage": "400000",
                        "operator": "Svenska kraftnät",
                        "cables": "6",
                        "description": "400kV Regional Transmission Grid",
                    },
                },
                {
                    "type": "node",
                    "id": 304567891,
                    "lat": lat - 0.004,
                    "lon": lon - 0.003,
                    "tags": {
                        "railway": "station",
                        "name": "Central Transport Hub",
                        "public_transport": "station",
                    },
                },
            ]

            raw_payload: Dict[str, Any] = {
                "coordinates": {"latitude": lat, "longitude": lon},
                "elements": mock_elements,
                "total_infra_elements": len(mock_elements),
                "mock": True,
            }

            # 1. Mast
            mast_node = EntityOutput(
                entity_type="Infrastructure",
                value=f"TelecomMast-{lat + 0.005:.4f}-{lon + 0.008:.4f}",
                attributes={
                    "subtype": "telecom_mast",
                    "operator": "Telia / Ericsson",
                    "height_m": 48,
                    "technology": "5G",
                    "latitude": lat + 0.005,
                    "longitude": lon + 0.008,
                },
                confidence_score=0.9,
            )
            entities.append(mast_node)

            # 2. Kraftledning
            power_node = EntityOutput(
                entity_type="Infrastructure",
                value="PowerGrid-400kV-SvenskaKraftnat",
                attributes={
                    "subtype": "power_line",
                    "voltage": "400kV",
                    "operator": "Svenska kraftnät",
                },
                confidence_score=0.95,
            )
            entities.append(power_node)

            # 3. Transportnav
            hub_node = EntityOutput(
                entity_type="Infrastructure",
                value="TransportHub-Central",
                attributes={"subtype": "railway_hub", "name": "Central Transport Hub"},
                confidence_score=0.9,
            )
            entities.append(hub_node)

            # Relationer
            for node in (mast_node, power_node, hub_node):
                relationships.append(
                    RelationOutput(
                        source_value=query_str,
                        target_value=node.value,
                        relation_type="SPATIAL_INFRASTRUCTURE",
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

        # Skarpt läge: anropa Overpass API
        delta = 0.05
        bbox = f"{lat - delta},{lon - delta},{lat + delta},{lon + delta}"
        overpass_ql = f"""[out:json][timeout:15];
(
  node["man_made"~"mast|tower"]({bbox});
  way["power"~"line|minor_line"]({bbox});
  node["public_transport"="station"]({bbox});
);
out body 15;
"""
        url = "https://overpass-api.de/api/interpreter"
        raw_payload = {"coordinates": f"{lat},{lon}", "bbox": bbox, "mock": False}

        try:
            resp = await opsec_client.post(url, data={"data": overpass_ql}, timeout=12.0)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                raw_payload["elements"] = elements
                for elem in elements[:10]:
                    tags = elem.get("tags", {})
                    elem_type = elem.get("type", "node")
                    elem_id = elem.get("id")
                    name = (
                        tags.get("name")
                        or tags.get("operator")
                        or tags.get("man_made")
                        or tags.get("power")
                        or f"{elem_type}-{elem_id}"
                    )

                    entities.append(
                        EntityOutput(
                            entity_type="Infrastructure",
                            value=f"OSM-{name}",
                            attributes={"tags": tags, "lat": elem.get("lat"), "lon": elem.get("lon")},
                            confidence_score=0.9,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=query_str,
                            target_value=f"OSM-{name}",
                            relation_type="SPATIAL_INFRASTRUCTURE",
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
