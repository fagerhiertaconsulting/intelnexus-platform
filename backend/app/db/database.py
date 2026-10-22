import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.config import settings
from app.models.case import Case, CaseCreateRequest, CaseUpdateRequest, CaseStatus, CasePriority, EgressPolicy
from app.models.entity import Entity, ProvenanceRecord, SourceReliability, InfoCredibility
from app.models.relationship import Relationship
from app.models.evidence import EvidenceItem


class DatabaseManager:
    """
    Trådsäkert persistenslager för Ärenden, Entiteter, Relationer och Bevis.
    Använder SQLite med JSON-stöd för zero-dependency lokal drift och full dataintegritet.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.DATA_DIR / "openintel.db")
        self._lock = threading.RLock()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")

            # Cases
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    egress_policy TEXT DEFAULT 'DIRECT',
                    tags TEXT,
                    investigator TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Entities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    aliases TEXT,
                    attributes TEXT,
                    provenance TEXT,
                    confidence_score REAL,
                    source_reliability TEXT DEFAULT 'B',
                    info_credibility INTEGER DEFAULT 2,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
                )
            """)

            # Relationships
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    attributes TEXT,
                    provenance TEXT,
                    confidence_score REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
                )
            """)

            # Evidence
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    source_url TEXT,
                    collector_plugin TEXT,
                    metadata TEXT,
                    source_reliability TEXT DEFAULT 'B',
                    info_credibility INTEGER DEFAULT 2,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
                )
            """)

            # Migrering för NATO Admiralty System kolumner om de saknas
            for table in ("entities", "evidence"):
                cursor.execute(f"PRAGMA table_info({table});")
                existing_cols = [c["name"] for c in cursor.fetchall()]
                if "source_reliability" not in existing_cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN source_reliability TEXT DEFAULT 'B';")
                if "info_credibility" not in existing_cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN info_credibility INTEGER DEFAULT 2;")

            # Migrering för OpSec egress_policy i cases
            cursor.execute("PRAGMA table_info(cases);")
            case_cols = [c["name"] for c in cursor.fetchall()]
            if "egress_policy" not in case_cols:
                cursor.execute("ALTER TABLE cases ADD COLUMN egress_policy TEXT DEFAULT 'DIRECT';")

            # 2FA User Settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_2fa_settings (
                    user_id TEXT PRIMARY KEY,
                    is_2fa_enabled INTEGER NOT NULL DEFAULT 0,
                    totp_secret_encrypted TEXT,
                    totp_verified INTEGER NOT NULL DEFAULT 0,
                    step_up_vault_required INTEGER NOT NULL DEFAULT 0,
                    elevated_until TEXT
                )
            """)

            # 2FA WebAuthn / FIDO2 Security Keys
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_security_keys (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    key_name TEXT NOT NULL,
                    credential_id TEXT NOT NULL UNIQUE,
                    public_key TEXT NOT NULL,
                    sign_count INTEGER NOT NULL DEFAULT 0,
                    transports TEXT DEFAULT '[]',
                    aaguid TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                )
            """)

            # 2FA Backup Recovery Codes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_backup_codes (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Index
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_case ON entities(case_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_case ON relationships(case_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id)")

            conn.commit()
            conn.close()

    # --- CASES ---

    def create_case(self, req: CaseCreateRequest) -> Case:
        status_val = req.status if isinstance(req.status, CaseStatus) else CaseStatus(req.status or "active")
        priority_val = (
            req.priority if isinstance(req.priority, CasePriority) else CasePriority(req.priority or "medium")
        )
        egress_val = (
            req.egress_policy
            if isinstance(req.egress_policy, EgressPolicy)
            else EgressPolicy(req.egress_policy or "DIRECT")
        )
        new_case = Case(
            title=req.title,
            description=req.description or "",
            status=status_val,
            priority=priority_val,
            egress_policy=egress_val,
            tags=req.tags or [],
            investigator=req.investigator or "Analyst",
        )
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cases (id, title, description, status, priority, egress_policy, tags, investigator, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    new_case.id,
                    new_case.title,
                    new_case.description,
                    new_case.status.value,
                    new_case.priority.value,
                    new_case.egress_policy.value,
                    json.dumps(new_case.tags),
                    new_case.investigator,
                    new_case.created_at.isoformat(),
                    new_case.updated_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return new_case

    def get_case(self, case_id: str, investigator: Optional[str] = None) -> Optional[Case]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if investigator:
                cursor.execute(
                    "SELECT * FROM cases WHERE id = ? AND (investigator = ? OR investigator = 'default_user' OR investigator = 'Analyst')",
                    (case_id, investigator),
                )
            else:
                cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return Case(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                status=row["status"],
                priority=row["priority"],
                egress_policy=EgressPolicy(row["egress_policy"] or "DIRECT"),
                tags=json.loads(row["tags"] or "[]"),
                investigator=row["investigator"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def list_cases(self, investigator: Optional[str] = None) -> List[Case]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if investigator:
                cursor.execute(
                    "SELECT * FROM cases WHERE investigator = ? OR investigator = 'default_user' OR investigator = 'Analyst' ORDER BY updated_at DESC",
                    (investigator,),
                )
            else:
                cursor.execute("SELECT * FROM cases ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [
                Case(
                    id=r["id"],
                    title=r["title"],
                    description=r["description"],
                    status=r["status"],
                    priority=r["priority"],
                    egress_policy=EgressPolicy(r["egress_policy"] or "DIRECT"),
                    tags=json.loads(r["tags"] or "[]"),
                    investigator=r["investigator"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
                for r in rows
            ]

    def update_case(self, case_id: str, req: CaseUpdateRequest, investigator: Optional[str] = None) -> Optional[Case]:
        existing = self.get_case(case_id, investigator=investigator)
        if not existing:
            return None

        updated_title = req.title if req.title is not None else existing.title
        updated_desc = req.description if req.description is not None else existing.description
        updated_status = req.status.value if req.status is not None else existing.status.value
        updated_priority = req.priority.value if req.priority is not None else existing.priority.value
        updated_egress = req.egress_policy.value if req.egress_policy is not None else existing.egress_policy.value
        updated_tags = req.tags if req.tags is not None else existing.tags
        updated_investigator = req.investigator if req.investigator is not None else existing.investigator
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE cases
                SET title = ?, description = ?, status = ?, priority = ?, egress_policy = ?, tags = ?, investigator = ?, updated_at = ?
                WHERE id = ?
            """,
                (
                    updated_title,
                    updated_desc,
                    updated_status,
                    updated_priority,
                    updated_egress,
                    json.dumps(updated_tags),
                    updated_investigator,
                    now,
                    case_id,
                ),
            )
            conn.commit()
            conn.close()

        return self.get_case(case_id, investigator=investigator)

    def delete_case(self, case_id: str, investigator: Optional[str] = None) -> bool:
        existing = self.get_case(case_id, investigator=investigator)
        if not existing:
            return False

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            cursor.execute("DELETE FROM entities WHERE case_id = ?", (case_id,))
            cursor.execute("DELETE FROM relationships WHERE case_id = ?", (case_id,))
            cursor.execute("DELETE FROM evidence WHERE case_id = ?", (case_id,))
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return affected > 0

            return affected > 0

    # --- ENTITIES ---

    def save_entity(self, entity: Entity) -> Entity:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            prov_json = json.dumps([p.model_dump(mode="json") for p in entity.provenance])
            cursor.execute(
                """
                INSERT INTO entities (id, case_id, type, name, aliases, attributes, provenance, confidence_score, source_reliability, info_credibility, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id=excluded.case_id,
                    type=excluded.type,
                    name=excluded.name,
                    aliases=excluded.aliases,
                    attributes=excluded.attributes,
                    provenance=excluded.provenance,
                    confidence_score=excluded.confidence_score,
                    source_reliability=excluded.source_reliability,
                    info_credibility=excluded.info_credibility,
                    updated_at=excluded.updated_at
            """,
                (
                    entity.id,
                    entity.case_id,
                    entity.type.value if hasattr(entity.type, "value") else str(entity.type),
                    entity.name,
                    json.dumps(entity.aliases),
                    json.dumps(entity.attributes),
                    prov_json,
                    entity.confidence_score,
                    entity.source_reliability.value
                    if hasattr(entity.source_reliability, "value")
                    else str(entity.source_reliability),
                    entity.info_credibility.value
                    if hasattr(entity.info_credibility, "value")
                    else int(entity.info_credibility),
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return self._row_to_entity(row)

    def list_entities(self, case_id: Optional[str] = None, entity_type: Optional[str] = None) -> List[Entity]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM entities WHERE 1=1"
            params = []
            if case_id:
                query += " AND case_id = ?"
                params.append(case_id)
            if entity_type:
                query += " AND type = ?"
                params.append(entity_type)
            query += " ORDER BY updated_at DESC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_entity(r) for r in rows]

    def delete_entity(self, entity_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            cursor.execute("DELETE FROM relationships WHERE source_id = ? OR target_id = ?", (entity_id, entity_id))
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return affected > 0

    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        prov_data = json.loads(row["provenance"] or "[]")
        provenance = [ProvenanceRecord(**p) for p in prov_data]
        keys = row.keys()
        source_rel = row["source_reliability"] if "source_reliability" in keys and row["source_reliability"] else "B"
        info_cred = row["info_credibility"] if "info_credibility" in keys and row["info_credibility"] is not None else 2
        return Entity(
            id=row["id"],
            case_id=row["case_id"],
            type=row["type"],
            name=row["name"],
            aliases=json.loads(row["aliases"] or "[]"),
            attributes=json.loads(row["attributes"] or "{}"),
            provenance=provenance,
            confidence_score=row["confidence_score"] or 1.0,
            source_reliability=SourceReliability(source_rel),
            info_credibility=InfoCredibility(int(info_cred)),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # --- RELATIONSHIPS ---

    def save_relationship(self, rel: Relationship) -> Relationship:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            prov_json = json.dumps([p.model_dump(mode="json") for p in rel.provenance])
            cursor.execute(
                """
                INSERT INTO relationships (id, case_id, source_id, target_id, relation_type, attributes, provenance, confidence_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id=excluded.case_id,
                    source_id=excluded.source_id,
                    target_id=excluded.target_id,
                    relation_type=excluded.relation_type,
                    attributes=excluded.attributes,
                    provenance=excluded.provenance,
                    confidence_score=excluded.confidence_score
            """,
                (
                    rel.id,
                    rel.case_id,
                    rel.source_id,
                    rel.target_id,
                    rel.relation_type.value,
                    json.dumps(rel.attributes),
                    prov_json,
                    rel.confidence_score,
                    rel.created_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return rel

    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM relationships WHERE id = ?", (rel_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return self._row_to_relationship(row)

    def list_relationships(self, case_id: Optional[str] = None) -> List[Relationship]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if case_id:
                cursor.execute("SELECT * FROM relationships WHERE case_id = ? ORDER BY created_at DESC", (case_id,))
            else:
                cursor.execute("SELECT * FROM relationships ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_relationship(r) for r in rows]

    def delete_relationship(self, rel_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM relationships WHERE id = ?", (rel_id,))
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return affected > 0

    def _row_to_relationship(self, row: sqlite3.Row) -> Relationship:
        prov_data = json.loads(row["provenance"] or "[]")
        provenance = [ProvenanceRecord(**p) for p in prov_data]
        return Relationship(
            id=row["id"],
            case_id=row["case_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation_type=row["relation_type"],
            attributes=json.loads(row["attributes"] or "{}"),
            provenance=provenance,
            confidence_score=row["confidence_score"] or 1.0,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # --- EVIDENCE ---

    def save_evidence(self, ev: EvidenceItem) -> EvidenceItem:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evidence (id, case_id, title, file_path, file_size_bytes, mime_type, sha256, source_url, collector_plugin, metadata, source_reliability, info_credibility, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    file_path=excluded.file_path,
                    file_size_bytes=excluded.file_size_bytes,
                    mime_type=excluded.mime_type,
                    sha256=excluded.sha256,
                    source_url=excluded.source_url,
                    collector_plugin=excluded.collector_plugin,
                    metadata=excluded.metadata,
                    source_reliability=excluded.source_reliability,
                    info_credibility=excluded.info_credibility
            """,
                (
                    ev.id,
                    ev.case_id,
                    ev.title,
                    ev.file_path,
                    ev.file_size_bytes,
                    ev.mime_type,
                    ev.sha256,
                    ev.source_url,
                    ev.collector_plugin,
                    json.dumps(ev.metadata),
                    ev.source_reliability.value
                    if hasattr(ev.source_reliability, "value")
                    else str(ev.source_reliability),
                    ev.info_credibility.value if hasattr(ev.info_credibility, "value") else int(ev.info_credibility),
                    ev.recorded_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return ev

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return self._row_to_evidence(row)

    def list_evidence(self, case_id: Optional[str] = None) -> List[EvidenceItem]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if case_id:
                cursor.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY recorded_at DESC", (case_id,))
            else:
                cursor.execute("SELECT * FROM evidence ORDER BY recorded_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_evidence(r) for r in rows]

    def _row_to_evidence(self, row: sqlite3.Row) -> EvidenceItem:
        keys = row.keys()
        source_rel = row["source_reliability"] if "source_reliability" in keys and row["source_reliability"] else "B"
        info_cred = row["info_credibility"] if "info_credibility" in keys and row["info_credibility"] is not None else 2
        return EvidenceItem(
            id=row["id"],
            case_id=row["case_id"],
            title=row["title"],
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            mime_type=row["mime_type"],
            sha256=row["sha256"],
            source_url=row["source_url"],
            collector_plugin=row["collector_plugin"],
            metadata=json.loads(row["metadata"] or "{}"),
            source_reliability=SourceReliability(source_rel),
            info_credibility=InfoCredibility(int(info_cred)),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    # --- 2FA & SECURITY ---

    def get_2fa_settings(self, user_id: str = "default_user") -> Dict[str, Any]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_2fa_settings WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    """
                    INSERT INTO user_2fa_settings (user_id, is_2fa_enabled, totp_secret_encrypted, totp_verified, step_up_vault_required, elevated_until)
                    VALUES (?, 0, NULL, 0, 0, NULL)
                """,
                    (user_id,),
                )
                conn.commit()
                cursor.execute("SELECT * FROM user_2fa_settings WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
            conn.close()
            return {
                "user_id": row["user_id"],
                "is_2fa_enabled": bool(row["is_2fa_enabled"]),
                "totp_secret_encrypted": row["totp_secret_encrypted"],
                "totp_verified": bool(row["totp_verified"]),
                "step_up_vault_required": bool(row["step_up_vault_required"]),
                "elevated_until": row["elevated_until"],
            }

    def update_2fa_settings(
        self,
        user_id: str = "default_user",
        is_2fa_enabled: Optional[bool] = None,
        totp_secret_encrypted: Optional[str] = None,
        totp_verified: Optional[bool] = None,
        step_up_vault_required: Optional[bool] = None,
        elevated_until: Optional[str] = None,
    ) -> Dict[str, Any]:
        current = self.get_2fa_settings(user_id)
        new_enabled = int(is_2fa_enabled if is_2fa_enabled is not None else current["is_2fa_enabled"])
        new_secret = totp_secret_encrypted if totp_secret_encrypted is not None else current["totp_secret_encrypted"]
        new_verified = int(totp_verified if totp_verified is not None else current["totp_verified"])
        new_step_up = int(
            step_up_vault_required if step_up_vault_required is not None else current["step_up_vault_required"]
        )
        new_elevated = elevated_until if elevated_until is not None else current["elevated_until"]

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_2fa_settings
                SET is_2fa_enabled = ?, totp_secret_encrypted = ?, totp_verified = ?, step_up_vault_required = ?, elevated_until = ?
                WHERE user_id = ?
            """,
                (new_enabled, new_secret, new_verified, new_step_up, new_elevated, user_id),
            )
            conn.commit()
            conn.close()

        return self.get_2fa_settings(user_id)

    def list_security_keys(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_security_keys WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "key_name": r["key_name"],
                    "credential_id": r["credential_id"],
                    "public_key": r["public_key"],
                    "sign_count": r["sign_count"],
                    "transports": json.loads(r["transports"] or "[]"),
                    "aaguid": r["aaguid"],
                    "created_at": r["created_at"],
                    "last_used_at": r["last_used_at"],
                }
                for r in rows
            ]

    def save_security_key(
        self,
        key_id: str,
        user_id: str,
        key_name: str,
        credential_id: str,
        public_key: str,
        sign_count: int = 0,
        transports: Optional[List[str]] = None,
        aaguid: Optional[str] = None,
    ):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_security_keys (id, user_id, key_name, credential_id, public_key, sign_count, transports, aaguid, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    key_id,
                    user_id,
                    key_name,
                    credential_id,
                    public_key,
                    sign_count,
                    json.dumps(transports or []),
                    aaguid,
                    now,
                    now,
                ),
            )
            conn.commit()
            conn.close()

    def get_security_key_by_credential_id(self, credential_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_security_keys WHERE credential_id = ?", (credential_id,))
            r = cursor.fetchone()
            conn.close()
            if not r:
                return None
            return {
                "id": r["id"],
                "user_id": r["user_id"],
                "key_name": r["key_name"],
                "credential_id": r["credential_id"],
                "public_key": r["public_key"],
                "sign_count": r["sign_count"],
                "transports": json.loads(r["transports"] or "[]"),
                "aaguid": r["aaguid"],
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
            }

    def update_security_key_sign_count(self, credential_id: str, sign_count: int):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_security_keys
                SET sign_count = ?, last_used_at = ?
                WHERE credential_id = ?
            """,
                (sign_count, now, credential_id),
            )
            conn.commit()
            conn.close()

    def delete_security_key(self, key_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_security_keys WHERE id = ?", (key_id,))
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return affected > 0

    def save_backup_codes(self, user_id: str, code_hashes: List[str]):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            for ch in code_hashes:
                from uuid import uuid4

                cursor.execute(
                    """
                    INSERT INTO user_backup_codes (id, user_id, code_hash, used_at, created_at)
                    VALUES (?, ?, ?, NULL, ?)
                """,
                    (f"code--{uuid4()}", user_id, ch, now),
                )
            conn.commit()
            conn.close()

    def list_unused_backup_codes(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_backup_codes WHERE user_id = ? AND used_at IS NULL", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"id": r["id"], "code_hash": r["code_hash"], "created_at": r["created_at"]} for r in rows]

    def mark_backup_code_used(self, code_id: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE user_backup_codes SET used_at = ? WHERE id = ?", (now, code_id))
            conn.commit()
            conn.close()

    def reset_2fa(self, user_id: str = "default_user"):
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_2fa_settings
                SET is_2fa_enabled = 0, totp_secret_encrypted = NULL, totp_verified = 0, step_up_vault_required = 0, elevated_until = NULL
                WHERE user_id = ?
            """,
                (user_id,),
            )
            cursor.execute("DELETE FROM user_security_keys WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM user_backup_codes WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()


db = DatabaseManager()
