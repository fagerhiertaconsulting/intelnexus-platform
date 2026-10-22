from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class CaseStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CasePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EgressPolicy(str, Enum):
    DIRECT = "DIRECT"
    PROXY_RESIDENTIAL = "PROXY_RESIDENTIAL"
    TOR_STRICT = "TOR_STRICT"


class Case(BaseModel):
    id: str = Field(default_factory=lambda: f"case--{uuid4()}", description="Unikt ID för utredningsärendet")
    title: str = Field(..., description="Rubrik på utredningen")
    description: str = Field(default="", description="Utredningsbeskrivning och hypotes")
    status: CaseStatus = Field(default=CaseStatus.ACTIVE)
    priority: CasePriority = Field(default=CasePriority.MEDIUM)
    egress_policy: EgressPolicy = Field(
        default=EgressPolicy.DIRECT,
        description="OpSec nätverkspolicy för utgående trafik (DIRECT, PROXY_RESIDENTIAL, TOR_STRICT)",
    )
    tags: List[str] = Field(
        default_factory=list, description="Taggar för kategorisering (t.ex. 'fraud', 'infrastructure')"
    )
    investigator: str = Field(default="Analyst", description="Ansvarig utredare")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    status: Optional[CaseStatus] = CaseStatus.ACTIVE
    priority: Optional[CasePriority] = CasePriority.MEDIUM
    egress_policy: Optional[EgressPolicy] = EgressPolicy.DIRECT
    tags: Optional[List[str]] = Field(default_factory=list)
    investigator: Optional[str] = "Analyst"


class CaseUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CaseStatus] = None
    priority: Optional[CasePriority] = None
    egress_policy: Optional[EgressPolicy] = None
    tags: Optional[List[str]] = None
    investigator: Optional[str] = None
