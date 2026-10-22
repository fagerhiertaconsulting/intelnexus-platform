from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: f"evidence--{uuid4()}", description="Unikt ID för bevisposten")
    case_id: str = Field(..., description="Kopplat ärende")
    title: str = Field(..., description="Beskrivning av beviset (t.ex. 'WHOIS raw response for target.com')")
    file_path: str = Field(..., description="Intern sökväg eller objekt-nyckel i lagringen")
    file_size_bytes: int = Field(default=0, description="Filstorlek i bytes")
    mime_type: str = Field(default="text/plain", description="MIME-typ (t.ex. 'application/json', 'image/png')")
    sha256: str = Field(..., description="Kryptografisk SHA-256 kontrollsumma som garanterar obruten beviskedja")
    source_url: Optional[str] = Field(None, description="Ursprunglig källa eller endpoint")
    collector_plugin: Optional[str] = Field(None, description="Modul som samlade in beviset")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Ytterligare metadata (headers, IP, statuskod)")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Tidpunkt för arkivering")


class EvidenceCreateRequest(BaseModel):
    case_id: str
    title: str
    source_url: Optional[str] = None
    collector_plugin: Optional[str] = None
    content: str
    mime_type: Optional[str] = "text/plain"
    metadata: Optional[Dict[str, Any]] = None
