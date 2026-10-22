from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, computed_field, field_validator


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    DOMAIN = "domain"
    IP = "ip"
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    CRYPTO_WALLET = "crypto_wallet"
    LOCATION = "location"
    DOCUMENT = "document"
    INCIDENT = "incident"


class SourceReliability(str, Enum):
    """NATO Admiralty System - Källans tillförlitlighet (A-F)."""

    A = "A"  # Helt tillförlitlig (Officiellt register, signerad data)
    B = "B"  # Oftast tillförlitlig (Välrenommerad källorganisation)
    C = "C"  # Ganska tillförlitlig
    D = "D"  # Inte vanligtvis tillförlitlig
    E = "E"  # Otillförlitlig
    F = "F"  # Tillförlitlighet kan inte bedömas


class InfoCredibility(int, Enum):
    """NATO Admiralty System - Informationens sannolikhet (1-6)."""

    CONFIRMED = 1  # Bekräftad av oberoende källor
    PROBABLE = 2  # Sannolik
    POSSIBLE = 3  # Möjlig
    DOUBTFUL = 4  # Tveksam
    IMPROBABLE = 5  # Osannolik
    CANNOT_BE_JUDGED = 6  # Kan inte bedömas

    # Numeriska alias för bekväm referens
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6


class ProvenanceRecord(BaseModel):
    source_url: str = Field(..., description="Käll-URL eller API-resurs där data inhämtades")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Tidsstämpel för hämtning"
    )
    sha256: str = Field(..., description="Kryptografisk SHA-256 kontrollsumma för rådata/svar")
    collector_plugin: str = Field(..., description="Namn på insamlingsmodulen (transform) som kördes")
    note: Optional[str] = Field(None, description="Valfri notering om proveniensen")
    source_reliability: SourceReliability = Field(
        default=SourceReliability.B, description="NATO Admiralty källtillförlitlighet (A-F)"
    )
    info_credibility: InfoCredibility = Field(
        default=InfoCredibility.PROBABLE, description="NATO Admiralty sannolikhetsgrad (1-6)"
    )

    @property
    def admiralty_code(self) -> str:
        rel = (
            self.source_reliability.value if hasattr(self.source_reliability, "value") else str(self.source_reliability)
        )
        cred = self.info_credibility.value if hasattr(self.info_credibility, "value") else str(self.info_credibility)
        return f"{rel}{cred}"


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: f"entity--{uuid4()}", description="Unikt ID med STIX 2.1-prefix")
    type: EntityType = Field(..., description="Entitetstyp")
    name: str = Field(..., description="Primärt visningsnamn eller identifierare")
    aliases: List[str] = Field(default_factory=list, description="Kända alias eller alternativa stavningar")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Nyckel-värde attribut")
    provenance: List[ProvenanceRecord] = Field(default_factory=list, description="Beviskedja och dataspårbarhet")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Konfidenspoäng mellan 0.0 och 1.0")
    case_id: Optional[str] = Field(None, description="Kopplat ärende-ID")
    source_reliability: SourceReliability = Field(
        default=SourceReliability.B, description="NATO Admiralty källtillförlitlighet (A-F)"
    )
    info_credibility: InfoCredibility = Field(
        default=InfoCredibility.PROBABLE, description="NATO Admiralty sannolikhetsgrad (1-6)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("type", mode="before")
    @classmethod
    def normalize_entity_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("ipaddress", "ip_address", "networkentity", "network_entity"):
                return EntityType.IP
            if v_clean in ("company", "organization"):
                return EntityType.ORGANIZATION
            try:
                return EntityType(v_clean)
            except ValueError:
                pass
        return v

    @field_validator("id")
    @classmethod
    def validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("entity--"):
            return f"entity--{v}"
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def admiralty_code(self) -> str:
        """Returnerar den kombinerade NATO Admiralty källkoden, t.ex. 'A1' eller 'B2'."""
        rel = (
            self.source_reliability.value if hasattr(self.source_reliability, "value") else str(self.source_reliability)
        )
        cred = self.info_credibility.value if hasattr(self.info_credibility, "value") else str(self.info_credibility)
        return f"{rel}{cred}"


class EntityCreateRequest(BaseModel):
    type: EntityType
    name: str
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    case_id: Optional[str] = None
    provenance_source: Optional[str] = None
    provenance_plugin: Optional[str] = None
    source_reliability: Optional[SourceReliability] = None
    info_credibility: Optional[InfoCredibility] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_entity_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("ipaddress", "ip_address", "networkentity", "network_entity"):
                return EntityType.IP
            if v_clean in ("company", "organization"):
                return EntityType.ORGANIZATION
            try:
                return EntityType(v_clean)
            except ValueError:
                pass
        return v
