"""Pruebas del cache acotado generico (eviction LRU + TTL opcional).

Cubre los 3 comportamientos que los forks necesitaban y resolvian a mano:
eviction por tamano maximo, expiracion por TTL, y que un acceso reciente
("LRU refresh") salve a una entrada vieja de ser evictada.
"""

import time

from core.bounded_cache import BoundedCache

# --- Construccion invalida ---

try:
    BoundedCache(max_size=0)
    raise AssertionError("max_size=0 deberia fallar")
except ValueError:
    pass

try:
    BoundedCache(max_size=10, ttl_seconds=0)
    raise AssertionError("ttl_seconds=0 deberia fallar")
except ValueError:
    pass

print("OK: construccion invalida rechazada")

# --- Eviction por tamano maximo ---

cache = BoundedCache[str, int](max_size=3)
cache.put("a", 1)
cache.put("b", 2)
cache.put("c", 3)
assert len(cache) == 3

cache.put("d", 4)
assert len(cache) == 3
assert "a" not in cache, "la entrada mas vieja (a) deberia haberse evictado"
assert "b" in cache
assert "c" in cache
assert "d" in cache

print("OK: eviction por tamano maximo evita la entrada mas vieja")

# --- LRU refresh: un get() reciente salva a la entrada de ser evictada ---

cache = BoundedCache[str, int](max_size=3)
cache.put("a", 1)
cache.put("b", 2)
cache.put("c", 3)

cache.get("a")  # "a" ya no es la menos recientemente usada

cache.put("d", 4)
assert "a" in cache, "a se refresco con get() y no deberia evictarse"
assert "b" not in cache, "b era la menos recientemente usada tras el get() de a"

print("OK: get() refresca LRU y evita eviction prematura")

# --- TTL opcional ---

cache = BoundedCache[str, int](max_size=10, ttl_seconds=0.05)
cache.put("x", 99)
assert cache.get("x") == 99
assert "x" in cache

time.sleep(0.08)

assert cache.get("x") is None, "la entrada deberia haber expirado por TTL"
assert "x" not in cache
assert len(cache) == 0, "la entrada expirada se purga al consultarla"

print("OK: TTL expira entradas y las purga de forma perezosa")

# --- Sin TTL, nunca expira por tiempo ---

cache = BoundedCache[str, int](max_size=10)
cache.put("y", 1)
time.sleep(0.05)
assert cache.get("y") == 1, "sin ttl_seconds no deberia expirar nunca"

print("OK: sin TTL las entradas no expiran")

# --- default en get() para key ausente ---

cache = BoundedCache[str, int](max_size=10)
assert cache.get("nunca-existio") is None
assert cache.get("nunca-existio", default=-1) == -1

print("OK: get() devuelve el default cuando la key no existe")

print("Todas las pruebas de BoundedCache pasaron.")
