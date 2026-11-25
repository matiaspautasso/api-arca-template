"""Caché simple en memoria con expiración por TTL (thread-safe)."""

import time
from threading import Lock
from typing import Callable


class TtlCache:
    def __init__(self, ttl_seconds: float, time_fn: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._time = time_fn
        self._data: dict = {}
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            valor, ts = entry
            if self._time() - ts > self._ttl:
                del self._data[key]
                return None
            return valor

    def set(self, key, valor) -> None:
        with self._lock:
            self._data[key] = (valor, self._time())
