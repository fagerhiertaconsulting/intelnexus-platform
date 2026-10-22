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


class NASAFIRMSPlugin(BaseOSINTPlugin):
    """
    GEOINT NASA FIRMS Satellite Thermal Anomaly Detector.
    Identifierar termiska anomalier, brandhärdar och kinetiska incidenter i realtid
    via NASA:s rymdbaserade VIIRS (S-NPP/NOAA-20) och MODIS (Terra/Aqua) sensorer.
    """

    plugin_id = "geoint_nasa_firms"
    name = "NASA FIRMS Satellite Thermal Anomaly Detector"
    category = PluginCategory.GEOINT
    nato_admiralty = "A2"
    requires_api_key = False  # Öppna data-feeds tillgängliga utan nyckel, nyckel för VIP API
    cost_per_query_usd = 0.0
    supported_entity_types = [
        "Coordinates",
        "BoundingBox",
        "Location",
        "coordinates",
        "boundingbox",
        "location",
    ]

    slug = "geoint_nasa_firms"
    description = "Satellitbaserad fjärranalys av markbränder, explosioner och termiska anomalier via NASA FIRMS."
    version = "1.0.0"
    output_entities = ["thermal_anomaly", "location", "satellite"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        coord_query = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        # Extrahera lat, lon om angivna som t.ex. "59.3293, 18.0686"
        lat, lon = 59.3293, 18.0686
        match = re.search(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", coord_query)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
            except ValueError:
                pass

        if is_mock_osint():
            hotspot_id = f"Hotspot-{lat:.3f}-{lon:.3f}"
            brightness_k = 342.5
            confidence = "nominal"
            satellite = "VIIRS S-NPP"
            acq_date = "2026-10-22"
            acq_time = "03:15 UTC"
            frp = 18.4  # MW

            raw_payload: Dict[str, Any] = {
                "coordinates": {"latitude": lat, "longitude": lon},
                "anomalies": [
                    {
                        "latitude": lat,
                        "longitude": lon,
                        "bright_ti4": brightness_k,
                        "scan": 0.4,
                        "track": 0.36,
                        "acq_date": acq_date,
                        "acq_time": acq_time,
                        "satellite": satellite,
                        "instrument": "VIIRS",
                        "confidence": confidence,
                        "version": "2.0NRT",
                        "bright_ti5": 294.2,
                        "frp": frp,
                        "daynight": "N",
                    }
                ],
                "mock": True,
            }

            anomaly_entity = EntityOutput(
                entity_type="ThermalAnomaly",
                value=hotspot_id,
                attributes={
                    "brightness_kelvin": brightness_k,
                    "confidence": confidence,
                    "satellite": satellite,
                    "frp_mw": frp,
                    "acquisition_time": f"{acq_date} {acq_time}",
                    "latitude": lat,
                    "longitude": lon,
                },
                confidence_score=0.98,
            )
            entities.append(anomaly_entity)

            loc_entity = EntityOutput(
                entity_type="Location",
                value=f"{lat:.4f},{lon:.4f}",
                attributes={"latitude": lat, "longitude": lon},
                confidence_score=1.0,
            )
            entities.append(loc_entity)

            relationships.append(
                RelationOutput(
                    source_value=hotspot_id,
                    target_value=f"{lat:.4f},{lon:.4f}",
                    relation_type="DETECTED_AT",
                    attributes={"admiralty": self.nato_admiralty, "satellite": satellite},
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
        firms_key = api_key or "open_firms_key"
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{firms_key}/VIIRS_SNPP_NRT/{lon - 0.1},{lat - 0.1},{lon + 0.1},{lat + 0.1}/1"
        headers = {"User-Agent": "IntelNexus-OSINT/1.0"}
        raw_payload = {"coordinates": f"{lat},{lon}", "mock": False}

        try:
            resp = await opsec_client.get(url, headers=headers, timeout=8.0)
            if resp.status_code == 200:
                csv_text = resp.text.strip()
                lines = csv_text.splitlines()
                raw_payload["csv_records_count"] = max(0, len(lines) - 1)
                if len(lines) > 1:
                    row = lines[1].split(",")
                    if len(row) >= 2:
                        h_id = f"Hotspot-{row[0]}-{row[1]}"
                        entities.append(
                            EntityOutput(
                                entity_type="ThermalAnomaly",
                                value=h_id,
                                attributes={"raw_csv": lines[1]},
                                confidence_score=0.95,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=coord_query,
                                target_value=h_id,
                                relation_type="OBSERVED_ANOMALY",
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
