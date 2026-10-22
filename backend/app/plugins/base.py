from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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


class TransformResult(BaseModel):
    """Enhetligt resultat från ett plugin-anrop."""

    entities: List[EntityOutput] = Field(default_factory=list, description="Upptäckta entiteter")
    relationships: List[RelationOutput] = Field(default_factory=list, description="Kopplade relationer")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Rådata från leverantörens API")


class BaseOSINTPlugin(ABC):
    """
    Standardiserad basklass för samtliga externa API- och inhämtningsplugins.
    Tillåter tredjepartsutvecklare att addera källor utan att modifiera plattformens kärnkod.
    """

    name: str
    slug: str
    description: str
    version: str = "1.0.0"

    # Valv- och autentiseringskrav
    required_vault_key: Optional[str] = None  # Matchas mot service_name i user_api_vault
    is_commercial: bool = False
    cost_per_query_estimate: float = 0.0  # Beräknad kostnad i krediter eller USD

    # Begränsningar och routing
    supported_inputs: List[str]  # Vilka entitetstyper pluginet kan expandera
    output_entities: List[str]  # Vilka entitetstyper pluginet producerar
    rate_limit_per_minute: int = 60
    supports_proxy: bool = True  # Om trafiken kan dirigeras via Tor/SOCKS5

    @abstractmethod
    async def execute(
        self,
        target: EntityInput,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> TransformResult:
        """Kör transformeringen asynkront och returnerar nya noder och kanter."""
        pass
