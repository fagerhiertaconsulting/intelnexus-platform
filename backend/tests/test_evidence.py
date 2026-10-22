import pytest
from app.db.object_store import object_store
from app.evidence.custody_manager import custody_manager
from app.models.case import CaseCreateRequest
from app.db.database import db


def test_object_store_integrity(tmp_path):
    store = object_store
    case_id = "test_custody_case"
    
    # Store text
    rel_path, sha, size = store.store_text(case_id, "evidence_1.txt", "Top Secret Intel Content")
    assert len(sha) == 64  # SHA-256 längd
    assert size > 0

    # Verify integrity
    assert store.verify_integrity(rel_path, sha) is True
    assert store.verify_integrity(rel_path, "0000000000000000000000000000000000000000000000000000000000000000") is False


def test_custody_audit():
    case = db.create_case(CaseCreateRequest(title="Audit Case"))
    cid = case.id

    # Spara två bevis
    rel_path1, sha1, size1 = object_store.store_text(cid, "ev1.json", '{"item": 1}')
    from app.models.evidence import EvidenceItem
    db.save_evidence(EvidenceItem(
        case_id=cid,
        title="Audit Item 1",
        file_path=rel_path1,
        file_size_bytes=size1,
        sha256=sha1,
    ))

    audit = custody_manager.verify_case_custody(cid)
    assert audit["chain_of_custody_intact"] is True
    assert audit["total_items"] >= 1
    assert audit["valid_count"] >= 1
