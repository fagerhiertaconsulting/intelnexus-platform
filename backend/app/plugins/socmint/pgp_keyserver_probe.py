import urllib.parse
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


class PGPKeyserverProbe(BaseOSINTPlugin):
    """
    SOCMINT PGP Keyserver Probe.
    Gör HKP-uppslag mot keys.openpgp.org och keyserver.ubuntu.com.
    Extraherar nyckel-ID, fingeravtryck, skapad-datum och alternativa användaridentiteter/e-postadresser.
    """

    plugin_id = "socmint_pgp_keyserver"
    name = "PGP Keyserver Identity Probe"
    category = PluginCategory.SOCMINT
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["Email", "EmailAddress", "KeyID", "PGPKey", "email", "pgpkey"]

    slug = "socmint_pgp_keyserver"
    description = "Slår upp publika PGP-krypteringsnycklar, certifikat och länkade identiteter via globala keyservers."
    version = "1.0.0"
    output_entities = ["pgpkey", "email", "person"]
    rate_limit_per_minute = 60
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        search_query = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            key_id = "0x4A89C19B22F9E83A"
            fingerprint = "E1B4905C3E9987F12A77B1094A89C19B22F9E83A"
            created_at = "2021-04-12T10:00:00Z"
            algo = "RSA-4096"
            uids = [search_query, f"security@{search_query.split('@')[-1] if '@' in search_query else 'example.com'}"]

            raw_payload: Dict[str, Any] = {
                "target": search_query,
                "keys": [
                    {
                        "key_id": key_id,
                        "fingerprint": fingerprint,
                        "created_at": created_at,
                        "algorithm": algo,
                        "user_identities": uids,
                    }
                ],
                "mock": True,
            }

            key_entity = EntityOutput(
                entity_type="PGPKey",
                value=fingerprint,
                attributes={
                    "key_id": key_id,
                    "fingerprint": fingerprint,
                    "algorithm": algo,
                    "created_at": created_at,
                },
                confidence_score=1.0,
            )
            entities.append(key_entity)

            relationships.append(
                RelationOutput(
                    source_value=search_query,
                    target_value=fingerprint,
                    relation_type="HAS_PGP_KEY",
                    attributes={"admiralty": self.nato_admiralty},
                )
            )

            for uid in uids:
                if uid != search_query and "@" in uid:
                    entities.append(
                        EntityOutput(
                            entity_type="Email",
                            value=uid,
                            attributes={"source": "PGP Keyserver UID"},
                            confidence_score=0.9,
                        )
                    )
                    relationships.append(
                        RelationOutput(
                            source_value=fingerprint,
                            target_value=uid,
                            relation_type="DECLARES_IDENTITY",
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

        # Skarpt läge: använd maskinläsbart HKP-gränssnitt från keyserver.ubuntu.com
        encoded = urllib.parse.quote(search_query)
        url = f"https://keyserver.ubuntu.com/pks/lookup?op=index&options=mr&search={encoded}"
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "text/plain"}
        raw_payload = {"target": search_query, "raw_hkp": "", "mock": False}

        try:
            resp = await opsec_client.get(url, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                raw_payload["raw_hkp"] = resp.text
                lines = resp.text.splitlines()
                current_key = None

                for line in lines:
                    parts = line.strip().split(":")
                    if not parts or not parts[0]:
                        continue
                    tag = parts[0]
                    if tag == "pub":
                        key_id = parts[1] if len(parts) > 1 else ""
                        algo = parts[2] if len(parts) > 2 else ""
                        created_ts = parts[4] if len(parts) > 4 else ""
                        current_key = key_id
                        entities.append(
                            EntityOutput(
                                entity_type="PGPKey",
                                value=key_id,
                                attributes={"algorithm": algo, "created_timestamp": created_ts},
                                confidence_score=1.0,
                            )
                        )
                        relationships.append(
                            RelationOutput(
                                source_value=search_query,
                                target_value=key_id,
                                relation_type="HAS_PGP_KEY",
                                attributes={"admiralty": self.nato_admiralty},
                            )
                        )
                    elif tag == "uid" and current_key:
                        uid_str = parts[1] if len(parts) > 1 else ""
                        if uid_str:
                            entities.append(
                                EntityOutput(
                                    entity_type="Identity",
                                    value=uid_str,
                                    attributes={"key_id": current_key},
                                    confidence_score=0.9,
                                )
                            )
                            relationships.append(
                                RelationOutput(
                                    source_value=current_key,
                                    target_value=uid_str,
                                    relation_type="DECLARES_IDENTITY",
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
