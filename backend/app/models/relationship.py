from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator
from .entity import ProvenanceRecord


class RelationshipType(str, Enum):
    OWNS = "OWNS"
    DIRECTOR_OF = "DIRECTOR_OF"
    EMPLOYEE_OF = "EMPLOYEE_OF"
    USES_IP = "USES_IP"
    TRANSACTED_TO = "TRANSACTED_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    RESOLVES_TO = "RESOLVES_TO"
    SUBDOMAIN_OF = "SUBDOMAIN_OF"
    HAS_ALIAS = "HAS_ALIAS"
    LOCATED_AT = "LOCATED_AT"
    REGISTERED_BY = "REGISTERED_BY"
    COMMUNICATES_WITH = "COMMUNICATES_WITH"
    FOUNDED_BY = "FOUNDED_BY"
    MEMBER_OF = "MEMBER_OF"


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: f"relationship--{uuid4()}", description="Unikt ID med STIX-prefix")
    source_id: str = Field(..., description="Källnodens entity-ID")
    target_id: str = Field(..., description="Målnodens entity-ID")
    relation_type: RelationshipType = Field(..., description="Typ av relation mellan noderna")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Attribut för kanten (t.ex. datum, roll, belopp)")
    provenance: List[ProvenanceRecord] = Field(default_factory=list, description="Proveniens för relationen")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Konfidenspoäng för relationen")
    case_id: Optional[str] = Field(None, description="Kopplat ärende")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id")
    @classmethod
    def validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("relationship--"):
            return f"relationship--{v}"
        return v


class RelationshipCreateRequest(BaseModel):
    source_id: str
    target_id: str
    relation_type: RelationshipType
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    case_id: Optional[str] = None
    provenance_source: Optional[str] = None
    provenance_plugin: Optional[str] = None
