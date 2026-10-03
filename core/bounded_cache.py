"""Cache acotado en memoria con eviction tipo LRU y TTL opcional.

Util para cualquier escenario donde se necesite recordar temporalmente un
conjunto de valores (dedup de eventos, resultados ya resueltos, contadores
por clave) sin que la memoria crezca sin limite. Thread-safe: puede
consultarse desde multiples hilos/tareas async a la vez sin condiciones
de carrera.
"""

from __future__ import annotations

import time 
from collections import OrderedDict
from threading import Lock
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


_SENTINEL = object()

class BoundedCache(Generic[K, V]):
    """Cache en memoria con tamano maximo fijo y TTL opcional.

    Eviction por tamano: la entrada menos recientemente usada (LRU) cuando
    se supera max_size. TTL opcional: una entrada expirada se trata como
    ausente en get/__contains__ y se purga perezosamente (sin hilo de
    limpieza en background).
    """
    def __init__(self, max_size: int, ttl_seconds: float | None = None) -> None:
        if max_size <= 0: 
            raise ValueError("max_size debe ser mayor que 0")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds debe ser mayor a 0 si se especifica")

        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._data: OrderedDict[K, tuple[V, float]] = OrderedDict()

    def put(self, key: K, value: V) -> None:
        with self._lock:
            self._data[key] = (value, time.monotonic())
            self._data.move_to_end(key)
            self._evict_if_needed()

    def get(self, key: K, default: V | None = None) -> V | None:
        with self._lock:
            entry = self._data.get(key, _SENTINEL)
            if entry is _SENTINEL:
                return default

            value, stored_at = entry
            if self._is_expired(stored_at):
                del self._data[key]
                return default

            self._data.move_to_end(key)
            return value

    def __contains__(self, key: K) -> bool:
        with self._lock:
            entry = self._data.get(key, _SENTINEL)
            if entry is _SENTINEL:
                return False

            _, stored_at = entry
            if self._is_expired(stored_at):
                del self._data[key]
                return False

            return True

            self._data.popitem(last=False)
