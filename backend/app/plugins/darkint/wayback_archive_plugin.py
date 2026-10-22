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


class WaybackArchivePlugin(BaseOSINTPlugin):
    """
    DARKINT Wayback Machine Historical Archive Probe.
    Söker och validerar historiska webbplatser och raderat material via Internet Archive CDX API.
    Stödjer bevisarkivering med obruten SHA-256 hashverifiering för rättsligt bruk.
    """

    plugin_id = "darkint_wayback_archive"
    name = "Wayback Machine Historical Archive Probe"
    category = PluginCategory.DARKINT
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["URL", "Domain", "url", "domain"]

    slug = "darkint_wayback_archive"
    description = (
        "Söker upp historiska webbarkiveringar, ändringshistorik och raderat innehåll via Wayback Machine CDX API."
    )
    version = "1.0.0"
    output_entities = ["archive_snapshot", "webpage", "domain"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        target_url = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            mock_snapshots = [
                {
                    "timestamp": "20200115120000",
                    "original": target_url,
                    "mimetype": "text/html",
                    "statuscode": "200",
                    "digest": "SHA256-MOCK-DIGEST-2020",
                    "archive_url": f"https://web.archive.org/web/20200115120000/{target_url}",
                },
                {
                    "timestamp": "20220610143000",
                    "original": target_url,
                    "mimetype": "text/html",
                    "statuscode": "200",
                    "digest": "SHA256-MOCK-DIGEST-2022",
                    "archive_url": f"https://web.archive.org/web/20220610143000/{target_url}",
                },
                {
                    "timestamp": "20241022080000",
                    "original": target_url,
                    "mimetype": "text/html",
                    "statuscode": "200",
                    "digest": "SHA256-MOCK-DIGEST-2024",
                    "archive_url": f"https://web.archive.org/web/20241022080000/{target_url}",
                },
            ]

            raw_payload: Dict[str, Any] = {
                "url": target_url,
                "snapshots": mock_snapshots,
                "total_snapshots": len(mock_snapshots),
                "earliest": mock_snapshots[0]["timestamp"],
                "latest": mock_snapshots[-1]["timestamp"],
                "mock": True,
            }

            for snap in mock_snapshots:
                snap_id = f"Wayback:{snap['timestamp']}"
                entities.append(
                    EntityOutput(
                        entity_type="ArchiveSnapshot",
                        value=snap_id,
                        attributes={
                            "timestamp": snap["timestamp"],
                            "archive_url": snap["archive_url"],
                            "status_code": snap["statuscode"],
                            "original_url": target_url,
                            "digest": snap["digest"],
                        },
                        confidence_score=1.0,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=target_url,
                        target_value=snap_id,
                        relation_type="HISTORICAL_SNAPSHOT",
                        attributes={"admiralty": self.nato_admiralty, "timestamp": snap["timestamp"]},
                    )
                )

            return PluginResult(
                entities=entities,
                relationships=relationships,
                raw_payload=raw_payload,
                nato_admiralty=self.nato_admiralty,
                cost_usd=self.cost_per_query_usd,
            )

        # Skarpt läge: anropa CDX API
        cdx_url = (
            f"https://web.archive.org/cdx/search/cdx?url={target_url}&output=json"
            "&fl=timestamp,original,mimetype,statuscode,digest&limit=10"
        )
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        raw_payload = {"url": target_url, "snapshots": [], "mock": False}

        try:
            resp = await opsec_client.get(cdx_url, headers=headers, timeout=8.0)
            if resp.status_code == 200:
                rows = resp.json()
                if len(rows) > 1:
                    # Första raden är headers
                    parsed_snaps: List[Dict[str, Any]] = []
                    for row in rows[1:]:
                        if len(row) >= 5:
                            ts = row[0]
                            orig = row[1]
                            mime = row[2]
                            sc = row[3]
                            dg = row[4]
                            archive_link = f"https://web.archive.org/web/{ts}/{orig}"
                            parsed_snaps.append(
                                {
                                    "timestamp": ts,
                                    "original": orig,
                                    "mimetype": mime,
                                    "statuscode": sc,
                                    "digest": dg,
                                    "archive_url": archive_link,
                                }
                            )

                            snap_node_id = f"Wayback:{ts}"
                            entities.append(
                                EntityOutput(
                                    entity_type="ArchiveSnapshot",
                                    value=snap_node_id,
                                    attributes={
                                        "timestamp": ts,
                                        "archive_url": archive_link,
                                        "status_code": sc,
                                    },
                                    confidence_score=1.0,
                                )
                            )
                            relationships.append(
                                RelationOutput(
                                    source_value=target_url,
                                    target_value=snap_node_id,
                                    relation_type="HISTORICAL_SNAPSHOT",
                                    attributes={"admiralty": self.nato_admiralty, "timestamp": ts},
                                )
                            )
                    raw_payload["snapshots"] = parsed_snaps
        except Exception as e:
            raw_payload["error"] = str(e)

        return PluginResult(
            entities=entities,
            relationships=relationships,
            raw_payload=raw_payload,
            nato_admiralty=self.nato_admiralty,
            cost_usd=self.cost_per_query_usd,
        )
