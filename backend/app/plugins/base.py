from abc import ABC, abstractmethod
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Union
import httpx
from pydantic import BaseModel, Field


class PluginCategory(str, Enum):
    """Kategorisering av OSINT-discipliner enligt standardiserat ramverk."""

    SOCMINT = "SOCMINT"
    FINMINT = "FINMINT"
    CTI = "CTI"
    GEOINT = "GEOINT"
    DARKINT = "DARKINT"


class EntityInput(BaseModel):
    """Indatakontrakt för plugin-anrop."""

    entity_type: str = Field(..., description="Entitetstyp, t.ex. 'Domain', 'IPAddress', 'Person', 'Company'")
    value: str = Field(..., description="Värde att slå upp, t.ex. domännamn, IP, namn eller org-nr")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Ytterligare kontext eller options")


class EntityOutput(BaseModel):
    """Utdataentitet genererad av ett plugin."""

    entity_type: str = Field(..., description="Entitetstyp för den upptäckta noden")
    value: str = Field(..., description="Primärt värde/identifierare för entiteten")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Attribut och detaljer")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Konfidenspoäng mellan 0.0 och 1.0")


class RelationOutput(BaseModel):
    """Utdatarelation mellan två entiteter."""

    source_value: str = Field(..., description="Källans värde/identifierare")
    target_value: str = Field(..., description="Målets värde/identifierare")
    relation_type: str = Field(..., description="Typ av relation, t.ex. 'RESOLVES_TO', 'OWNED_BY', 'OPERATES_ON'")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Attribut för kanten")


class PluginResult(BaseModel):
    """Enhetligt resultat från ett plugin-anrop med NATO-betyg och SHA-256 beviskedja."""

    entities: List[EntityOutput] = Field(default_factory=list, description="Upptäckta entiteter")
    relationships: List[RelationOutput] = Field(default_factory=list, description="Kopplade relationer")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Rådata från leverantörens API")
    evidence_hash: str = Field(default="", description="SHA-256 hash av rådata för beviskedjan")
    cached: bool = Field(default=False, description="Indikerar om svaret hämtades från cache")
    nato_admiralty: str = Field(default="A1", description="NATO Admiralty-bedömning (t.ex. A1, B2)")
    cost_usd: float = Field(default=0.0, description="Beräknad eller upplupen API-kostnad i USD")


# Bakåtkompatibilitet för TransformResult
TransformResult = PluginResult


class BaseOSINTPlugin(ABC):
    """
    Standardiserad basklass för samtliga externa API- och inhämtningsplugins.
    Tillåter tredjepartsutvecklare och moduler att addera källor utan att modifiera plattformens kärnkod.
    """

    plugin_id: str = ""
    name: str = ""
    category: PluginCategory = PluginCategory.SOCMINT
    nato_admiralty: str = "A1"
    requires_api_key: bool = False
    cost_per_query_usd: float = 0.0
    supported_entity_types: List[str] = []

    # Bakåtkompatibilitet
    slug: str = ""
    description: str = ""
    version: str = "1.0.0"
    required_vault_key: Optional[str] = None
    is_commercial: bool = False
    cost_per_query_estimate: float = 0.0
    supported_inputs: List[str] = []
    output_entities: List[str] = []
    rate_limit_per_minute: int = 60
    supports_proxy: bool = True

    def __init__(self):
        # Synka fält mellan specifikation och bakåtkompatibilitet
        if not getattr(self, "slug", "") and getattr(self, "plugin_id", ""):
            self.slug = self.plugin_id
        elif not getattr(self, "plugin_id", "") and getattr(self, "slug", ""):
            self.plugin_id = self.slug

        if not getattr(self, "supported_inputs", None) and getattr(self, "supported_entity_types", None):
            self.supported_inputs = list(self.supported_entity_types)
        elif not getattr(self, "supported_entity_types", None) and getattr(self, "supported_inputs", None):
            self.supported_entity_types = list(self.supported_inputs)

        if getattr(self, "cost_per_query_usd", 0.0) > 0 and getattr(self, "cost_per_query_estimate", 0.0) == 0.0:
            self.cost_per_query_estimate = self.cost_per_query_usd
            self.is_commercial = True
        elif getattr(self, "cost_per_query_estimate", 0.0) > 0 and getattr(self, "cost_per_query_usd", 0.0) == 0.0:
            self.cost_per_query_usd = self.cost_per_query_estimate
            self.is_commercial = True

        if getattr(self, "requires_api_key", False) and not getattr(self, "required_vault_key", None):
            self.required_vault_key = f"{self.plugin_id.upper()}_API_KEY"
        elif getattr(self, "required_vault_key", None) and not getattr(self, "requires_api_key", False):
            self.requires_api_key = True

    async def execute(
        self,
        target: Union[str, EntityInput],
        opsec_client: Optional[httpx.AsyncClient] = None,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
        skip_cache: bool = False,
    ) -> PluginResult:
        """
        Kör transformeringen asynkront och returnerar nya noder, relationer,
        automatisk SHA-256 beviskedjehashning och Redis-cachestöd.
        """
        if isinstance(target, EntityInput):
            target_val = target.value.strip()
            target_type = target.entity_type.strip()
        else:
            target_val = str(target).strip()
            target_type = self.supported_entity_types[0] if self.supported_entity_types else "Unknown"

        from app.core.finops.cache import response_cache

        # 1. Kontrollera cache (om ej skip_cache)
        plugin_key = self.plugin_id or self.slug or self.__class__.__name__
        if not skip_cache:
            cached_data = response_cache.get(plugin_key, target_type, target_val)
            if cached_data:
                cached_entities = [EntityOutput(**e) for e in cached_data.get("entities", [])]
                cached_relations = [RelationOutput(**r) for r in cached_data.get("relationships", [])]
                return PluginResult(
                    entities=cached_entities,
                    relationships=cached_relations,
                    raw_payload=cached_data.get("raw_payload", {}),
                    evidence_hash=cached_data.get("evidence_hash", ""),
                    cached=True,
                    nato_admiralty=self.nato_admiralty,
                    cost_usd=0.0,
                )

        # 2. Skapa HTTP-klient om ingen tillhandahållits
        client_to_close: Optional[httpx.AsyncClient] = None
        client = opsec_client
        if client is None:
            client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
            client_to_close = client

        try:
            res = await self._execute(target_val, client, api_key=api_key, proxy_url=proxy_url)
        finally:
            if client_to_close is not None:
                await client_to_close.aclose()

        # 3. SHA-256 automatisk beviskedjehash
        if not res.evidence_hash:
            raw_bytes = json.dumps(res.raw_payload, sort_keys=True, default=str).encode("utf-8")
            res.evidence_hash = hashlib.sha256(raw_bytes).hexdigest()

        # 4. Sätt NATO Admiralty-klassificering och kostnad
        if not res.nato_admiralty:
            res.nato_admiralty = self.nato_admiralty
        if res.cost_usd == 0.0 and self.cost_per_query_usd > 0.0:
            res.cost_usd = self.cost_per_query_usd

        # 5. Spara i cache
        response_cache.set(
            plugin_key,
            target_type,
            target_val,
            res.model_dump(),
        )

        return res

    @abstractmethod
    async def _execute(
        self,
        target: str,
        opsec_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        """Kärnimplementering för subklasser."""
        pass
