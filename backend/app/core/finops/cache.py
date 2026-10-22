import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional
from app.config import settings

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]


class ResponseCache:
    """
    Svars-caching och determinationsbaserad deduplicering för externa API-anrop.

    Cache-nyckel: SHA256(plugin_slug + target_type + target_value)
    Standard TTL:
      - 24 timmar för statisk data (WHOIS, företagsregister)
      - 2 timmar för dynamisk nätverksdata (DNS, IP)
    """

    STATIC_TYPES = {"whois", "company", "organization", "person", "registry"}

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        self._lock = threading.Lock()
        self._memory_cache: Dict[str, Any] = {}

        url = redis_url or getattr(settings, "REDIS_URL", None) or "redis://localhost:6379/0"
        if redis is not None and url:
            try:
                client = redis.from_url(url, decode_responses=True, socket_timeout=1.0)
                client.ping()
                self.redis_client = client
            except Exception:
                self.redis_client = None

    @staticmethod
    def compute_key(plugin_slug: str, target_type: str, target_value: str) -> str:
        """Beräknar deterministisk SHA-256 hash för förfrågan."""
        raw = f"{plugin_slug.strip().lower()}:{target_type.strip().lower()}:{target_value.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_default_ttl(self, target_type: str) -> int:
        """Returnerar 24 timmar (86400s) för statisk data och 2 timmar (7200s) för dynamisk."""
        clean_type = target_type.strip().lower()
        if any(s in clean_type for s in self.STATIC_TYPES):
            return 86400  # 24h
        return 7200  # 2h

    get_ttl_for_target = get_default_ttl

    def get(self, plugin_slug: str, target_type: str, target_value: str) -> Optional[Dict[str, Any]]:
        """Hämtar cachat svar om giltigt."""
        cache_key = self.compute_key(plugin_slug, target_type, target_value)
        now = time.time()

        if self.redis_client:
            try:
                cached_json = self.redis_client.get(f"finops:cache:{cache_key}")
                if cached_json:
                    return json.loads(cached_json)
            except Exception:
                pass

        with self._lock:
            entry = self._memory_cache.get(cache_key)
            if entry:
                if now < entry["expires_at"]:
                    return entry["data"]
                self._memory_cache.pop(cache_key, None)
        return None

    def set(
        self,
        plugin_slug: str,
        target_type: str,
        target_value: str,
        result: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ):
        """Sparar svar med TTL."""
        cache_key = self.compute_key(plugin_slug, target_type, target_value)
        ttl = ttl_seconds if ttl_seconds is not None else self.get_default_ttl(target_type)
        now = time.time()

        if self.redis_client:
            try:
                self.redis_client.setex(
                    f"finops:cache:{cache_key}",
                    ttl,
                    json.dumps(result),
                )
            except Exception:
                pass

        with self._lock:
            self._memory_cache[cache_key] = {
                "data": result,
                "expires_at": now + ttl,
            }

    def delete(self, plugin_slug: str, target_type: str, target_value: str):
        """Tar bort en specifik cache-post (t.ex. vid force refresh)."""
        cache_key = self.compute_key(plugin_slug, target_type, target_value)
        if self.redis_client:
            try:
                self.redis_client.delete(f"finops:cache:{cache_key}")
            except Exception:
                pass
        with self._lock:
            self._memory_cache.pop(cache_key, None)

    invalidate = delete

    def clear(self):
        """Rensar hela cachen."""
        with self._lock:
            self._memory_cache.clear()


response_cache = ResponseCache()
