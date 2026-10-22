import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx
from app.db.database import db
from app.db.object_store import object_store
from app.models.evidence import EvidenceItem


class CustodyManager:
    """
    Hanterar beviskedja (Chain of Custody) och automatisk webbarkivering med
    kryptografisk SHA-256 hashning och verifiering.
    """

    async def capture_web_snapshot(self, url: str, case_id: str, title: Optional[str] = None) -> EvidenceItem:
        """
        Hämtar och fryser en webbsida i oföränderlig lagring med SHA-256 hash
        och lagrar HTTP-huvuden, tidsstämpel och statuskod.
        """
        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenIntel-Archiver/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(clean_url, headers=headers)
            html_content = resp.text
            status_code = resp.status_code
            resp_headers = dict(resp.headers)

        timestamp_str = int(time.time())
        clean_host = clean_url.replace("https://", "").replace("http://", "").split("/")[0]
        filename = f"snapshot_{clean_host}_{timestamp_str}.html"

        # Spara rå HTML
        rel_path, sha256_hash, size = object_store.store_text(
            case_id=case_id,
            filename=filename,
            content=html_content,
            subfolder="snapshots",
        )

        # Spara även tillhörande HTTP metadata
        meta_payload = {
            "url": clean_url,
            "status_code": status_code,
            "headers": resp_headers,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "html_sha256": sha256_hash,
            "size_bytes": size,
        }
        object_store.store_json(
            case_id=case_id,
            filename=f"meta_{clean_host}_{timestamp_str}.json",
            data_dict=meta_payload,
            subfolder="snapshots",
        )

        evidence = EvidenceItem(
            case_id=case_id,
            title=title or f"Web Snapshot of {clean_url}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="text/html",
            sha256=sha256_hash,
            source_url=clean_url,
            collector_plugin="web_snapshotter",
            metadata={"status_code": status_code, "host": clean_host},
        )

        db.save_evidence(evidence)
        return evidence

    def verify_case_custody(self, case_id: str) -> Dict[str, Any]:
        """
        Granskar alla bevisfiler för ett ärende och verifierar deras kryptografiska
        SHA-256 hash mot beviskedjeloggen.
        """
        evidence_list = db.list_evidence(case_id=case_id)
        verified = []
        tampered = []
        missing = []

        for ev in evidence_list:
            try:
                is_valid = object_store.verify_integrity(ev.file_path, ev.sha256)
                if is_valid:
                    verified.append(
                        {
                            "id": ev.id,
                            "title": ev.title,
                            "sha256": ev.sha256,
                            "file_path": ev.file_path,
                            "status": "VALID",
                        }
                    )
                else:
                    tampered.append(
                        {
                            "id": ev.id,
                            "title": ev.title,
                            "expected_sha256": ev.sha256,
                            "status": "HASH_MISMATCH",
                        }
                    )
            except FileNotFoundError:
                missing.append(
                    {
                        "id": ev.id,
                        "title": ev.title,
                        "status": "FILE_NOT_FOUND",
                    }
                )

        all_ok = len(tampered) == 0 and len(missing) == 0

        return {
            "case_id": case_id,
            "total_items": len(evidence_list),
            "valid_count": len(verified),
            "tampered_count": len(tampered),
            "missing_count": len(missing),
            "chain_of_custody_intact": all_ok,
            "verified_items": verified,
            "tampered_items": tampered,
            "missing_items": missing,
            "audited_at": datetime.now(timezone.utc).isoformat(),
        }


custody_manager = CustodyManager()
