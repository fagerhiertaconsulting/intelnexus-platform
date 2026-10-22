from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


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


class ProvenanceRecord(BaseModel):
    source_url: str = Field(..., description="Käll-URL eller API-resurs där data inhämtades")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Tidsstämpel för hämtning")
    sha256: str = Field(..., description="Kryptografisk SHA-256 kontrollsumma för rådata/svar")
    collector_plugin: str = Field(..., description="Namn på insamlingsmodulen (transform) som kördes")
    note: Optional[str] = Field(None, description="Valfri notering om proveniensen")


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: f"entity--{uuid4()}", description="Unikt ID med STIX 2.1-prefix")
    type: EntityType = Field(..., description="Entitetstyp")
    name: str = Field(..., description="Primärt visningsnamn eller identifierare")
    aliases: List[str] = Field(default_factory=list, description="Kända alias eller alternativa stavningar")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Nyckel-värde attribut")
    provenance: List[ProvenanceRecord] = Field(default_factory=list, description="Beviskedja och dataspårbarhet")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Konfidenspoäng mellan 0.0 och 1.0")
    case_id: Optional[str] = Field(None, description="Kopplat ärende-ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id")
    @classmethod
    def validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("entity--"):
            return f"entity--{v}"
        return v


class EntityCreateRequest(BaseModel):
    type: EntityType
    name: str
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    case_id: Optional[str] = None
    provenance_source: Optional[str] = None
    provenance_plugin: Optional[str] = None
