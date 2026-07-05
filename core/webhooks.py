"""Verificacion generica de webhooks entrantes.

Cada proveedor (Meta/WhatsApp, Shopify, etc.) firma sus webhooks con HMAC
sobre el cuerpo crudo del request usando un secreto compartido. Esta funcion
es el primitivo reutilizable; cada canal solo aporta el nombre del header y
el algoritmo que use su proveedor.
"""

import hashlib
import hmac


def verify_hmac_signature(
    payload: bytes,
    signature: str | None,
    secret: str,
    *,
    algorithm: str = "sha256",
    prefix: str = "",
) -> bool:
    """Compara una firma HMAC recibida contra la calculada localmente.

    `prefix` es para formatos tipo Meta, que mandan "sha256=<hex>" en vez de
    solo el hex. Usa comparacion de tiempo constante (hmac.compare_digest).
    """
    if not signature or not secret:
        return False

    expected = hmac.new(secret.encode(), payload, getattr(hashlib, algorithm)).hexdigest()
    expected_with_prefix = f"{prefix}{expected}"

    return hmac.compare_digest(signature, expected_with_prefix)
