"""Pruebas del fail-fast de settings: sin API key del provider elegido, el
servidor debe tronar al arrancar con mensaje claro, no a medio request."""

from unittest.mock import patch

from core.settings import settings

# Caso 1: sin key del provider -> RuntimeError con mensaje accionable
with patch.multiple(settings, llm_provider="google", google_api_key=None):
    try:
        settings.require_llm_api_key()
        raise AssertionError("debio tronar sin API key")
    except RuntimeError as exc:
        assert "google" in str(exc)
        assert "GOOGLE_API_KEY" in str(exc)
print("OK: sin API key truena al arrancar con mensaje claro")

# Caso 2: con key, la regresa tal cual
with patch.multiple(settings, llm_provider="google", google_api_key="k-123"):
    assert settings.require_llm_api_key() == "k-123"
print("OK: con API key la regresa")

# Caso 3: provider desconocido tambien truena (active_llm_api_key da None)
with patch.multiple(settings, llm_provider="inventado"):
    try:
        settings.require_llm_api_key()
        raise AssertionError("debio tronar con provider desconocido")
    except RuntimeError:
        pass
print("OK: provider desconocido truena")

print("\nTodas las pruebas de settings pasaron.")
