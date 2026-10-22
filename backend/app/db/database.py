import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings
from app.models.case import Case, CaseCreateRequest, CaseUpdateRequest
from app.models.entity import Entity, ProvenanceRecord
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
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Cases
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
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
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
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
        new_case = Case(
            title=req.title,
            description=req.description or "",
            status=req.status or "active",
            priority=req.priority or "medium",
            tags=req.tags or [],
            investigator=req.investigator or "Analyst",
        )
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cases (id, title, description, status, priority, tags, investigator, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_case.id,
                new_case.title,
                new_case.description,
                new_case.status.value,
                new_case.priority.value,
                json.dumps(new_case.tags),
                new_case.investigator,
                new_case.created_at.isoformat(),
                new_case.updated_at.isoformat(),
            ))
            conn.commit()
            conn.close()
        return new_case

    def get_case(self, case_id: str) -> Optional[Case]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
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
                tags=json.loads(row["tags"] or "[]"),
                investigator=row["investigator"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def list_cases(self) -> List[Case]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
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
                    tags=json.loads(r["tags"] or "[]"),
                    investigator=r["investigator"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
                for r in rows
            ]

    def update_case(self, case_id: str, req: CaseUpdateRequest) -> Optional[Case]:
        existing = self.get_case(case_id)
        if not existing:
            return None
        
        updated_title = req.title if req.title is not None else existing.title
        updated_desc = req.description if req.description is not None else existing.description
        updated_status = req.status.value if req.status is not None else existing.status.value
        updated_priority = req.priority.value if req.priority is not None else existing.priority.value
        updated_tags = req.tags if req.tags is not None else existing.tags
        updated_investigator = req.investigator if req.investigator is not None else existing.investigator
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE cases
                SET title = ?, description = ?, status = ?, priority = ?, tags = ?, investigator = ?, updated_at = ?
                WHERE id = ?
            """, (
                updated_title,
                updated_desc,
                updated_status,
                updated_priority,
                json.dumps(updated_tags),
                updated_investigator,
                now,
                case_id,
            ))
            conn.commit()
            conn.close()

        return self.get_case(case_id)

    def delete_case(self, case_id: str) -> bool:
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

    # --- ENTITIES ---

    def save_entity(self, entity: Entity) -> Entity:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            prov_json = json.dumps([p.model_dump(mode="json") for p in entity.provenance])
            cursor.execute("""
                INSERT INTO entities (id, case_id, type, name, aliases, attributes, provenance, confidence_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id=excluded.case_id,
                    type=excluded.type,
                    name=excluded.name,
                    aliases=excluded.aliases,
                    attributes=excluded.attributes,
                    provenance=excluded.provenance,
                    confidence_score=excluded.confidence_score,
                    updated_at=excluded.updated_at
            """, (
                entity.id,
                entity.case_id,
                entity.type.value,
                entity.name,
                json.dumps(entity.aliases),
                json.dumps(entity.attributes),
                prov_json,
                entity.confidence_score,
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
            ))
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
        return Entity(
            id=row["id"],
            case_id=row["case_id"],
            type=row["type"],
            name=row["name"],
            aliases=json.loads(row["aliases"] or "[]"),
            attributes=json.loads(row["attributes"] or "{}"),
            provenance=provenance,
            confidence_score=row["confidence_score"] or 1.0,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # --- RELATIONSHIPS ---

    def save_relationship(self, rel: Relationship) -> Relationship:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            prov_json = json.dumps([p.model_dump(mode="json") for p in rel.provenance])
            cursor.execute("""
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
            """, (
                rel.id,
                rel.case_id,
                rel.source_id,
                rel.target_id,
                rel.relation_type.value,
                json.dumps(rel.attributes),
                prov_json,
                rel.confidence_score,
                rel.created_at.isoformat(),
            ))
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
            cursor.execute("""
                INSERT INTO evidence (id, case_id, title, file_path, file_size_bytes, mime_type, sha256, source_url, collector_plugin, metadata, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    file_path=excluded.file_path,
                    file_size_bytes=excluded.file_size_bytes,
                    mime_type=excluded.mime_type,
                    sha256=excluded.sha256,
                    source_url=excluded.source_url,
                    collector_plugin=excluded.collector_plugin,
                    metadata=excluded.metadata
            """, (
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
                ev.recorded_at.isoformat(),
            ))
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
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )


db = DatabaseManager()
