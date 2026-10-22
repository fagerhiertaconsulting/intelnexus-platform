from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from app.models.entity import Entity, EntityType, ProvenanceRecord
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from app.core.vault import credential_vault, LocalCredentialVault


class TransformResult(BaseModel):
    transform_name: str
    success: bool
    seed_id: str
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    logs: List[str] = Field(default_factory=list)
    unlocked_by_credentials: List[str] = Field(default_factory=list)


class BaseTransform(ABC):
    """
    Abstrakt basklass för alla OSINT-transforms.
    Stödjer BYOAK (Bring Your Own API Key) med automatisk avkänning av nödvändiga
    krypterade API-nycklar i det lokala valvet.
    """
    name: str = "base_transform"
    display_name: str = "Base Transform"
    description: str = "Baskonverterare"
    category: str = "general"
    supported_types: Set[EntityType] = set()
    required_credentials: List[str] = []  # Lista över nyckelnamn i CredentialVault (t.ex. 'SHODAN_API_KEY')

    def is_available(self, vault: Optional[LocalCredentialVault] = None) -> bool:
        """
        Returnerar True om alla nödvändiga API-nycklar finns konfigurerade i användarens valv.
        Om required_credentials är tom (gratiskälla) är den alltid tillgänglig.
        """
        if not self.required_credentials:
            return True
        v = vault or credential_vault
        return all(v.has_key(k) for k in self.required_credentials)

    def validate_input(self, entity: Entity) -> bool:
        """Validerar att indataentiteten stöds av denna transform."""
        if entity.type not in self.supported_types:
            return False
        if not entity.name or len(entity.name.strip()) == 0:
            return False
        return True

    @abstractmethod
    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        """
        Kör datainsamling mot externa källor och returnerar ett TransformResult.
        Alla hämtade data ska generera ett evidens-objekt med SHA-256.
        """
        pass

    def create_provenance(self, source_url: str, sha256: str, note: Optional[str] = None) -> ProvenanceRecord:
        """Skapar en standardiserad provenienspost för skapade entiteter."""
        return ProvenanceRecord(
            source_url=source_url,
            timestamp=datetime.now(timezone.utc),
            sha256=sha256,
            collector_plugin=self.name,
            note=note,
        )
