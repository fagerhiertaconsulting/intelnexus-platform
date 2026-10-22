import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple
from app.config import settings


class ObjectStore:
    """
    Kryptografisk bevislagring med automatisk SHA-256 beräkning och integritetskontroll.
    Stödjer både lokal filsystems- och S3/MinIO-abstraktion.
    """
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.EVIDENCE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        """Beräknar SHA-256 hash för binär data."""
        return hashlib.sha256(data).hexdigest()

    def store_bytes(self, case_id: str, filename: str, data: bytes, subfolder: str = "") -> Tuple[str, str, int]:
        """
        Lagrar rå binärdata i ärendets beviskatalog.
        Returnerar: (relativ sökväg, sha256_hash, filstorlek_bytes)
        """
        target_dir = self.base_dir / case_id / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        
        file_sha256 = self.calculate_sha256(data)
        file_path = target_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(data)
            
        relative_path = str(file_path.relative_to(self.base_dir))
        return relative_path, file_sha256, len(data)

    def store_text(self, case_id: str, filename: str, content: str, subfolder: str = "") -> Tuple[str, str, int]:
        """Lagrar stränginnehåll kodat som UTF-8."""
        data = content.encode("utf-8")
        return self.store_bytes(case_id, filename, data, subfolder)

    def store_json(self, case_id: str, filename: str, data_dict: dict, subfolder: str = "") -> Tuple[str, str, int]:
        """Lagrar serialiserad JSON med stabil sortering för reproducerbar hashning."""
        serialized = json.dumps(data_dict, indent=2, sort_keys=True).encode("utf-8")
        return self.store_bytes(case_id, filename, serialized, subfolder)

    def read_bytes(self, relative_path: str) -> bytes:
        """Läser in rådata från lagringen."""
        full_path = self.base_dir / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"Bevisfil saknas: {relative_path}")
        with open(full_path, "rb") as f:
            return f.read()

    def read_text(self, relative_path: str) -> str:
        """Läser in textdata från lagringen."""
        return self.read_bytes(relative_path).decode("utf-8")

    def verify_integrity(self, relative_path: str, expected_sha256: str) -> bool:
        """
        Validerar att bevisfilen på disk inte har manipulerats genom att jämföra dess faktiska
        SHA-256 hash med den förväntade hashen i beviskedjan.
        """
        try:
            data = self.read_bytes(relative_path)
            actual_sha256 = self.calculate_sha256(data)
            return actual_sha256.lower() == expected_sha256.lower()
        except Exception:
            return False


object_store = ObjectStore()
