import hashlib
import hmac
import secrets
from typing import List
from app.db.database import db

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BACKUP_CODE_SALT = "openintel_backup_code_salt_v1_"


def _hash_code(code: str) -> str:
    cleaned = code.strip().upper().replace(" ", "").replace("-", "")
    salted = f"{BACKUP_CODE_SALT}{cleaned}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


class BackupCodeService:
    @staticmethod
    def generate_code_string() -> str:
        """Skapar en läsbar 8-teckens kod i formatet XXXX-XXXX utan tvetydiga tecken."""
        part1 = "".join(secrets.choice(ALPHABET) for _ in range(4))
        part2 = "".join(secrets.choice(ALPHABET) for _ in range(4))
        return f"{part1}-{part2}"

    @classmethod
    def generate_and_save_backup_codes(cls, user_id: str = "default_user", count: int = 8) -> List[str]:
        """
        Genererar `count` nya engångskoder, sparar deras hash i databasen,
        och returnerar klartextkoderna så att användaren kan spara dem.
        """
        raw_codes = [cls.generate_code_string() for _ in range(count)]
        code_hashes = [_hash_code(c) for c in raw_codes]
        db.save_backup_codes(user_id, code_hashes)
        return raw_codes

    @staticmethod
    def verify_and_redeem_code(user_id: str = "default_user", code: str = "") -> bool:
        """
        Verifierar om koden matchar en oanvänd nödkod.
        Om giltig, markeras den som förbrukad direkt (single-use).
        """
        if not code or not code.strip():
            return False

        input_hash = _hash_code(code)
        unused_codes = db.list_unused_backup_codes(user_id)

        for item in unused_codes:
            stored_hash = item["code_hash"]
            if hmac.compare_digest(stored_hash, input_hash):
                db.mark_backup_code_used(item["id"])
                return True

        return False
