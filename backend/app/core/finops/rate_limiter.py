import threading
import time
from typing import Any, Dict, Optional
from app.config import settings

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]


class TokenBucketRateLimiter:
    """
    FinOps Token Bucket hastighetsbegränsare via Redis med automatisk in-memory fallback.

    Formel:
        Tokens_t = min(Kapacitet, Tokens_{t-1} + delta_t * RefillRate)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_capacity: int = 60,
        default_refill_rate: float = 1.0,
    ):
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.redis_client = None
        self._lock = threading.Lock()
        self._memory_buckets: Dict[str, Any] = {}

        url = redis_url or getattr(settings, "REDIS_URL", None) or "redis://localhost:6379/0"
        if redis is not None and url:
            try:
                client = redis.from_url(url, decode_responses=True, socket_timeout=1.0)
                client.ping()
                self.redis_client = client
            except Exception:
                self.redis_client = None

    def acquire(
        self,
        key: str,
        cost: int = 1,
        capacity: Optional[int] = None,
        refill_rate: Optional[float] = None,
        max_tokens: Optional[int] = None,
        refill_rate_per_sec: Optional[float] = None,
    ) -> bool:
        """
        Försöker allokera `cost` tokens ur hinken för angiven nyckel.
        Returnerar True om tokens fanns och förbrukades, annars False.
        """
        cap = capacity if capacity is not None else (max_tokens if max_tokens is not None else self.default_capacity)
        rate = (
            refill_rate
            if refill_rate is not None
            else (refill_rate_per_sec if refill_rate_per_sec is not None else self.default_refill_rate)
        )

        if self.redis_client:
            try:
                return self._acquire_redis(key, cost, cap, rate)
            except Exception:
                # Fallback till minne om Redis tappar anslutning
                pass

        return self._acquire_memory(key, cost, cap, rate)

    def _acquire_memory(self, key: str, cost: int, capacity: int, refill_rate: float) -> bool:
        now = time.time()
        with self._lock:
            if key not in self._memory_buckets:
                self._memory_buckets[key] = {
                    "tokens": float(capacity),
                    "last_refill": now,
                    "capacity": capacity,
                    "refill_rate": refill_rate,
                }

            bucket = self._memory_buckets[key]
            delta = max(0.0, now - bucket["last_refill"])
            bucket["tokens"] = min(float(capacity), bucket["tokens"] + delta * refill_rate)
            bucket["last_refill"] = now

            if bucket["tokens"] >= cost:
                bucket["tokens"] -= cost
                return True
            return False

    def _acquire_redis(self, key: str, cost: int, capacity: int, refill_rate: float) -> bool:
        # Atomic token bucket check & update in Redis
        now = time.time()
        redis_key = f"finops:ratelimit:{key}"
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local cost = tonumber(ARGV[2])
        local capacity = tonumber(ARGV[3])
        local refill_rate = tonumber(ARGV[4])

        local data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(data[1])
        local last_refill = tonumber(data[2])

        if not tokens or not last_refill then
            tokens = capacity
            last_refill = now
        else
            local delta = math.max(0, now - last_refill)
            tokens = math.min(capacity, tokens + delta * refill_rate)
            last_refill = now
        end

        if tokens >= cost then
            tokens = tokens - cost
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 60)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            return 0
        end
        """
        assert self.redis_client is not None
        result = self.redis_client.eval(lua_script, 1, redis_key, now, cost, capacity, refill_rate)
        return bool(result == 1)

    def get_available_tokens(
        self,
        key: str,
        capacity: Optional[int] = None,
        refill_rate: Optional[float] = None,
    ) -> float:
        """Hämtar aktuellt antal tillgängliga tokens i hinken."""
        cap = capacity if capacity is not None else self.default_capacity
        rate = refill_rate if refill_rate is not None else self.default_refill_rate
        now = time.time()

        if self.redis_client:
            try:
                redis_key = f"finops:ratelimit:{key}"
                data = self.redis_client.hmget(redis_key, ["tokens", "last_refill"])
                if data and data[0] is not None and data[1] is not None:
                    tokens = float(data[0])
                    last_refill = float(data[1])
                    delta = max(0.0, now - last_refill)
                    return min(float(cap), tokens + delta * rate)
                return float(cap)
            except Exception:
                pass

        with self._lock:
            if key not in self._memory_buckets:
                return float(cap)
            bucket = self._memory_buckets[key]
            delta = max(0.0, now - bucket["last_refill"])
            return min(float(cap), bucket["tokens"] + delta * rate)

    def reset(self, key: str):
        """Återställer en hink."""
        with self._lock:
            self._memory_buckets.pop(key, None)
        if self.redis_client:
            try:
                self.redis_client.delete(f"finops:ratelimit:{key}")
            except Exception:
                pass

    def get_status(
        self,
        key: str,
        capacity: Optional[int] = None,
        refill_rate: Optional[float] = None,
    ) -> dict:
        """Returnerar aktuell kvotstatus för en specifik resurs eller plugin."""
        with self._lock:
            if key in self._memory_buckets:
                cap = capacity if capacity is not None else self._memory_buckets[key]["capacity"]
                rate = refill_rate if refill_rate is not None else self._memory_buckets[key]["refill_rate"]
            else:
                cap = capacity if capacity is not None else self.default_capacity
                rate = refill_rate if refill_rate is not None else self.default_refill_rate

        available = self.get_available_tokens(key, cap, rate)
        backend = "redis" if self.redis_client else "memory"
        return {
            "key": key,
            "current_tokens": available,
            "capacity": cap,
            "refill_rate": rate,
            "backend": backend,
        }


rate_limiter = TokenBucketRateLimiter()
