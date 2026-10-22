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


class CryptoMempoolPlugin(BaseOSINTPlugin):
    """
    FINMINT Mempool.space Bitcoin Address Intelligence.
    Asynkront uppslag mot mempool.space/api/address/{addr} för Bitcoin-adresser.
    Returnerar transaktionssummor, bekräftade UTXO, historik och aktuellt saldo.
    """

    plugin_id = "finmint_crypto_mempool"
    name = "Mempool.space Bitcoin Intelligence"
    category = PluginCategory.FINMINT
    nato_admiralty = "A1"
    requires_api_key = False
    cost_per_query_usd = 0.0
    supported_entity_types = ["CryptoAddress", "BitcoinAddress", "Wallet", "cryptoaddress", "bitcoinaddress", "wallet"]

    slug = "finmint_crypto_mempool"
    description = "Slår upp on-chain transaktionsdata, UTXO-balanser och plånbokshistorik för Bitcoin."
    version = "1.0.0"
    output_entities = ["wallet", "transaction", "cryptoaddress"]
    rate_limit_per_minute = 100
    supports_proxy = True

    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        address = target.strip()
        entities: List[EntityOutput] = []
        relationships: List[RelationOutput] = []

        if is_mock_osint():
            funded_sat = 520000000  # 5.2 BTC
            spent_sat = 410000000  # 4.1 BTC
            balance_sat = funded_sat - spent_sat  # 1.1 BTC
            tx_count = 42

            raw_payload: Dict[str, Any] = {
                "address": address,
                "chain_stats": {
                    "funded_txo_count": 28,
                    "funded_txo_sum": funded_sat,
                    "spent_txo_count": 14,
                    "spent_txo_sum": spent_sat,
                    "tx_count": tx_count,
                },
                "mempool_stats": {
                    "funded_txo_count": 1,
                    "funded_txo_sum": 10000000,
                    "spent_txo_count": 0,
                    "spent_txo_sum": 0,
                    "tx_count": 1,
                },
                "balance_btc": balance_sat / 100000000.0,
                "total_received_btc": funded_sat / 100000000.0,
                "mock": True,
            }

            wallet_node = EntityOutput(
                entity_type="CryptoWallet",
                value=address,
                attributes={
                    "currency": "BTC",
                    "balance_btc": balance_sat / 100000000.0,
                    "total_received_btc": funded_sat / 100000000.0,
                    "tx_count": tx_count,
                    "source": "mempool.space",
                },
                confidence_score=1.0,
            )
            entities.append(wallet_node)

            relationships.append(
                RelationOutput(
                    source_value=address,
                    target_value=f"BTC-Balance:{balance_sat / 100000000.0}",
                    relation_type="HAS_BALANCE",
                    attributes={"admiralty": self.nato_admiralty, "currency": "BTC"},
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
        url = f"https://mempool.space/api/address/{address}"
        headers = {"User-Agent": "IntelNexus-OSINT/1.0", "Accept": "application/json"}
        raw_payload = {"address": address, "mock": False}

        try:
            resp = await opsec_client.get(url, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                data = resp.json()
                chain_stats = data.get("chain_stats", {})
                funded_sat = chain_stats.get("funded_txo_sum", 0)
                spent_sat = chain_stats.get("spent_txo_sum", 0)
                balance_sat = funded_sat - spent_sat
                tx_count = chain_stats.get("tx_count", 0)

                balance_btc = balance_sat / 100000000.0
                received_btc = funded_sat / 100000000.0

                data["balance_btc"] = balance_btc
                data["total_received_btc"] = received_btc
                raw_payload = data

                entities.append(
                    EntityOutput(
                        entity_type="CryptoWallet",
                        value=address,
                        attributes={
                            "currency": "BTC",
                            "balance_btc": balance_btc,
                            "total_received_btc": received_btc,
                            "tx_count": tx_count,
                        },
                        confidence_score=1.0,
                    )
                )
                relationships.append(
                    RelationOutput(
                        source_value=address,
                        target_value=f"BTC-Balance:{balance_btc}",
                        relation_type="HAS_BALANCE",
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
