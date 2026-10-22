import base64
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from app.config import settings


# Katalog över stödda API-tjänster enligt specifikation v2
SUPPORTED_API_SERVICES: Dict[str, Dict[str, Any]] = {
    # Svenska & Nordiska register
    "BOLAGSVERKET_API_KEY": {
        "service": "Bolagsverket",
        "domain": "corporate",
        "label": "Bolagsverket API (Företagsdata)",
        "description": "Officiella svenska bolagshandlingar, styrelser och årsredovisningar.",
        "requires_paid": True,
    },
    "INFOTORG_API_KEY": {
        "service": "InfoTorg",
        "domain": "corporate",
        "label": "InfoTorg Person & Företag",
        "description": "Folkbokföringsdata, fordon, fastighetsregister och firmatecknare.",
        "requires_paid": True,
    },
    "ROARING_API_KEY": {
        "service": "Roaring",
        "domain": "corporate",
        "label": "Roaring Nordic Business API",
        "description": "Verkliga huvudmän (UBO), kreditstatus och koncernstrukturer.",
        "requires_paid": True,
    },
    # Internationella bolag & AML
    "OPENCORPORATES_API_KEY": {
        "service": "OpenCorporates",
        "domain": "corporate",
        "label": "OpenCorporates Commercial API",
        "description": "Global databas med över 200 miljoner internationella bolag.",
        "requires_paid": False,
    },
    "OPENSANCTIONS_API_KEY": {
        "service": "OpenSanctions",
        "domain": "compliance",
        "label": "OpenSanctions API",
        "description": "Sanktionslistor, PEP (Politiskt exponerade personer) och brottsregister.",
        "requires_paid": False,
    },
    # Cyber & Infrastruktur
    "SHODAN_API_KEY": {
        "service": "Shodan",
        "domain": "cyber",
        "label": "Shodan Enterprise API",
        "description": "Öppna portar, banners, sårbarheter och IoT-infrastruktur.",
        "requires_paid": True,
    },
    "VIRUSTOTAL_API_KEY": {
        "service": "VirusTotal",
        "domain": "cyber",
        "label": "VirusTotal Enterprise API",
        "description": "Skadlig kod, domänrykte och hotaktörsanalys.",
        "requires_paid": False,
    },
    "CENSYS_API_ID": {
        "service": "Censys",
        "domain": "cyber",
        "label": "Censys Search API",
        "description": "Certifikatsträd, värdar och global nätverksskanning.",
        "requires_paid": True,
    },
    # Geointelligens & Rörelse
    "NASA_FIRMS_KEY": {
        "service": "NASA FIRMS",
        "domain": "geoint",
        "label": "NASA FIRMS (Satellitbrand/Värmedata)",
        "description": "Realtidsdata över bränder och termiska anomalier i kriszoner.",
        "requires_paid": False,
    },
    "OPENSKY_CREDENTIALS": {
        "service": "OpenSky Network",
        "domain": "geoint",
        "label": "OpenSky Network (ADS-B Transpondrar)",
        "description": "Flygspårning och luftrumsrörelser via ADS-B data.",
        "requires_paid": False,
    },
    # Kryptovalutor
    "ETHERSCAN_API_KEY": {
        "service": "Etherscan",
        "domain": "crypto",
        "label": "Etherscan API",
        "description": "Ethereum och ERC-20 plånbokstransaktioner och smarta kontrakt.",
        "requires_paid": False,
    },
    # Sociala medier & Säkerhet
    "HIBP_API_KEY": {
        "service": "HaveIBeenPwned",
        "domain": "security",
        "label": "HaveIBeenPwned API",
        "description": "Kontroll av e-post och telefonnummer mot kända dataläckor.",
        "requires_paid": True,
    },
}


class LocalCredentialVault:
    """
    Lokalt valv för användarens API-nycklar (BYOAK).
    Krypterar alla hemligheter i vila med AES-256-GCM.
    Härleder krypteringsnyckeln från användarens lokala masterlösenord.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.DATA_DIR / "openintel.db")
        self._lock = threading.RLock()
        self._master_secret = settings.JWT_SECRET.encode("utf-8")
        self._salt = b"openintel_aes_gcm_salt_2026_local"
        self._init_vault_db()

    def _derive_aes_key(self) -> bytes:
        """Härleder en 256-bitars nyckel för AES-GCM via PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
        )
        return kdf.derive(self._master_secret)

    def _init_vault_db(self):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credential_vault (
                    key_name TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    label TEXT NOT NULL,
                    encrypted_value TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()

    def set_key(self, key_name: str, secret_value: str, label: Optional[str] = None):
        """Krypterar och sparar en API-nyckel i det lokala valvet."""
        aes_key = self._derive_aes_key()
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)  # 96-bit nonce för GCM

        encrypted_bytes = aesgcm.encrypt(nonce, secret_value.encode("utf-8"), None)
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode("ascii")
        nonce_b64 = base64.b64encode(nonce).decode("ascii")

        service_meta = SUPPORTED_API_SERVICES.get(key_name, {})
        service_title = service_meta.get("service", key_name)
        display_label = label or service_meta.get("label", key_name)

        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO credential_vault (key_name, service, label, encrypted_value, nonce, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key_name) DO UPDATE SET
                    encrypted_value=excluded.encrypted_value,
                    nonce=excluded.nonce,
                    updated_at=excluded.updated_at
            """, (key_name, service_title, display_label, encrypted_b64, nonce_b64, now, now))
            conn.commit()
            conn.close()

    def get_key(self, key_name: str) -> Optional[str]:
        """Dekrypterar och returnerar API-nyckeln i klartext."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT encrypted_value, nonce FROM credential_vault WHERE key_name = ?", (key_name,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            try:
                encrypted_bytes = base64.b64decode(row["encrypted_value"])
                nonce = base64.b64decode(row["nonce"])
                aes_key = self._derive_aes_key()
                aesgcm = AESGCM(aes_key)
                decrypted = aesgcm.decrypt(nonce, encrypted_bytes, None)
                return decrypted.decode("utf-8")
            except Exception:
                return None

    def has_key(self, key_name: str) -> bool:
        """Kontrollerar om en giltig API-nyckel finns konfigurerad i valvet."""
        val = self.get_key(key_name)
        return bool(val and len(val.strip()) > 0)

    def delete_key(self, key_name: str) -> bool:
        """Raderar en nyckel från valvet."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM credential_vault WHERE key_name = ?", (key_name,))
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return affected > 0

    def list_configured_keys(self) -> List[Dict[str, Any]]:
        """Listar alla konfigurerade nycklar i maskerad form (t.ex. sk-***1234)."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT key_name, service, label, created_at, updated_at FROM credential_vault ORDER BY service ASC")
            rows = cursor.fetchall()
            conn.close()

            configured = {}
            for r in rows:
                key_name = r["key_name"]
                raw_val = self.get_key(key_name) or ""
                if len(raw_val) > 8:
                    masked = f"{raw_val[:3]}...{raw_val[-4:]}"
                else:
                    masked = "***"

                configured[key_name] = {
                    "key_name": key_name,
                    "service": r["service"],
                    "label": r["label"],
                    "is_configured": True,
                    "masked_value": masked,
                    "updated_at": r["updated_at"],
                }

            # Sammanställ med hela katalogen
            result = []
            for k, meta in SUPPORTED_API_SERVICES.items():
                if k in configured:
                    result.append({
                        **configured[k],
                        "domain": meta["domain"],
                        "description": meta["description"],
                        "requires_paid": meta["requires_paid"],
                    })
                else:
                    result.append({
                        "key_name": k,
                        "service": meta["service"],
                        "label": meta["label"],
                        "domain": meta["domain"],
                        "description": meta["description"],
                        "requires_paid": meta["requires_paid"],
                        "is_configured": False,
                        "masked_value": None,
                        "updated_at": None,
                    })

            return result


credential_vault = LocalCredentialVault()
