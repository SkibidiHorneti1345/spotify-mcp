import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Hashable


_MISSING = object()


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Small in-memory TTL cache for process-local MCP tool results."""

    def __init__(self, clock: Callable[[], float] | None = None):
        self._clock = clock or time.monotonic
        self._entries: dict[tuple[str, Hashable], _CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, namespace: str, key: Hashable, default: Any = None) -> Any:
        cache_key = (namespace, key)
        now = self._clock()
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is None:
                return default
            if entry.expires_at <= now:
                self._entries.pop(cache_key, None)
                return default
            return entry.value

    def set(self, namespace: str, key: Hashable, value: Any, ttl_seconds: float) -> Any:
        cache_key = (namespace, key)
        expires_at = self._clock() + ttl_seconds
        with self._lock:
            self._entries[cache_key] = _CacheEntry(value=value, expires_at=expires_at)
        return value

    def get_or_set(
        self,
        namespace: str,
        key: Hashable,
        ttl_seconds: float,
        factory: Callable[[], Any],
    ) -> Any:
        cached = self.get(namespace, key, _MISSING)
        if cached is not _MISSING:
            return cached

        value = factory()
        return self.set(namespace, key, value, ttl_seconds)

    def invalidate(self, namespace: str, key: Hashable) -> None:
        with self._lock:
            self._entries.pop((namespace, key), None)

    def invalidate_namespace(self, namespace: str) -> None:
        with self._lock:
            for cache_key in list(self._entries):
                if cache_key[0] == namespace:
                    self._entries.pop(cache_key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
