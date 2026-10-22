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


class OpenSkyADSBPlugin(BaseOSINTPlugin):
    """
    GEOINT OpenSky Network ADS-B Flight Tracking Plugin.
    Hämtar realtidsdata för civila och statliga luftfartyg via OpenSky Network API.
    Extraherar ICAO 24-bit transponderadresser, anropssignaler (callsigns),
    position (lat/long), barometrisk flyghöjd och markhastighet.
    """

    plugin_id = "geoint_opensky_adsb"
    name = "OpenSky Network ADS-B Aircraft Tracker"
    category = PluginCategory.GEOINT
    nato_admiralty = "A2"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = [
        "Aircraft",
        "Flight",
        "ICAO24",
        "Callsign",
        "aircraft",
        "flight",
        "icao24",
        "callsign",
    ]

    slug = "geoint_opensky_adsb"
    description = (
        "Realtidsspårning av flygrörelser, transponderpositioner och luftrum via OpenSky Network ADS-B-mottagare."
    )
    version = "1.0.0"
    output_entities = ["aircraft", "flight", "location"]
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

        # Detektera om målet är ICAO24 hex-adress (t.ex. 4bb0e1) eller callsign (t.ex. SAS142)
        is_icao_hex = bool(re.match(r"^[0-9a-f]{6}$", query, re.IGNORECASE))
        icao_hex = query.lower() if is_icao_hex else "4bb0e1"
        callsign = query.upper() if not is_icao_hex else "SAS142"

        if is_mock_osint():
            lat = 59.3293
            lon = 18.0686
            baro_alt = 10668.0  # meter (ca FL350)
            velocity = 235.5  # m/s
            origin_country = "Sweden"

            raw_payload: Dict[str, Any] = {
                "time": 1774166400,
                "states": [
                    [
                        icao_hex,
                        f"{callsign} ",
                        origin_country,
                        1774166400,
                        1774166400,
                        lon,
                        lat,
                        baro_alt,
                        False,  # on_ground
                        velocity,
                        182.4,  # true_track
                        0.0,  # vertical_rate
                        None,
                        baro_alt,
                        None,
                        False,
                        0,
                    ]
                ],
                "mock": True,
            }

            aircraft_node = EntityOutput(
                entity_type="Aircraft",
                value=f"ICAO:{icao_hex}",
                attributes={
                    "icao24": icao_hex,
                    "callsign": callsign,
                    "country": origin_country,
                    "altitude_meters": baro_alt,
                    "velocity_mps": velocity,
                    "latitude": lat,
                    "longitude": lon,
                },
                confidence_score=0.95,
            )
            entities.append(aircraft_node)

            flight_node = EntityOutput(
                entity_type="Flight",
                value=callsign,
                attributes={"icao24": icao_hex, "origin_country": origin_country},
                confidence_score=0.9,
            )
            entities.append(flight_node)

            loc_node = EntityOutput(
                entity_type="Location",
                value=f"{lat:.4f},{lon:.4f}",
                attributes={"altitude_m": baro_alt, "airspace": "Stockholm FIR"},
                confidence_score=0.95,
            )
            entities.append(loc_node)

            relationships.append(
                RelationOutput(
                    source_value=f"ICAO:{icao_hex}",
                    target_value=callsign,
                    relation_type="OPERATED_AS",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )
            relationships.append(
                RelationOutput(
                    source_value=f"ICAO:{icao_hex}",
                    target_value=f"{lat:.4f},{lon:.4f}",
                    relation_type="CURRENT_POSITION",
                    attributes={"admiralty": self.nato_admiralty, "altitude_m": baro_alt},
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
        url = "https://opensky-network.org/api/states/all"
        params = {"icao24": icao_hex} if is_icao_hex else {}
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        raw_payload = {"target": query, "mock": False}

        try:
            resp = await opsec_client.get(url, params=params, headers=headers, timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_payload["opensky_data"] = data
                states = data.get("states", [])
                if states:
                    s = states[0]
                    found_icao = str(s[0])
                    found_callsign = str(s[1]).strip()
                    found_country = str(s[2])
                    found_lon = s[5]
                    found_lat = s[6]
                    found_alt = s[7]

                    entities.append(
                        EntityOutput(
                            entity_type="Aircraft",
                            value=f"ICAO:{found_icao}",
                            attributes={
                                "callsign": found_callsign,
                                "country": found_country,
                                "alt": found_alt,
                                "latitude": found_lat,
                                "longitude": found_lon,
                            },
                            confidence_score=0.95,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=query,
                            target_value=f"ICAO:{found_icao}",
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
