"""Settings del bot, leidos del .env y validados.

Una sola fuente de verdad para la config. Cambias el .env -> cambias
el comportamiento, sin tocar codigo. Cada fork tiene su propio .env.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

# Proveedor -> variable de entorno de su API key.
PROVEEDORES_LLM = {
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # proveedor del LLM
    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"
    # Tope de razonamiento (openai y openrouter): sin el, un modelo que razona
    # puede gastar todo max_tokens pensando y devolver la respuesta vacia.
    llm_reasoning_effort: str | None = None

    # Modelo de respaldo: si la llamada al primario sale vacia, cortada o con
    # error, esa llamada se repite con este modelo. Opcional.
    llm_fallback_provider: str | None = None
    llm_fallback_model: str | None = None
    llm_fallback_reasoning_effort: str | None = None

    # logging: DEBUG saca las trazas con datos de la persona que escribe
    log_level: str = "INFO"

    # tipo de memoria
    memory_kind: str = "memory"
    postgres_url: str | None = None

    # API keys (opcionales; usas la del provider elegido)
    google_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    handoff_policy: str = "default"

    # seguridad de endpoints
    chat_api_key: str | None = None
    kommo_webhook_secret: str | None = None
    max_message_length: int = 4000

    # Si esta vacio, el reporte de errores se queda solo en logging local
    # (ver core/error_reporting.py).
    sentry_dsn: str | None = None

    # Zona horaria del negocio. La usa la normalizacion de fechas relativas
    # ("mañana", "el sabado"): sin ella el servidor resolveria contra UTC y
    # despues de las 18:00 local ya estaria contestando con el dia siguiente.
    business_timezone: str = "America/Mexico_City"

    def _api_key_de(self, provider: str | None) -> str | None:
        api_keys = {
            "google": self.google_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "openrouter": self.openrouter_api_key,
        }
        return api_keys.get(provider or "")

    @property
    def active_llm_api_key(self) -> str | None:
        return self._api_key_de(self.llm_provider)

    def require_llm_api_key(self) -> str:
        """Fail-fast al arrancar: mejor tronar aqui que a medio request.

        Se llama desde el bootstrap del servidor, no al importar, para que
        los tests puros (sin .env) sigan corriendo.
        """
        key = self.active_llm_api_key
        if not key:
            raise RuntimeError(
                f"Falta la API key para el provider '{self.llm_provider}'. "
                "Revisa el .env (GOOGLE_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY / "
                "OPENROUTER_API_KEY)."
            )
        return key

    def require_fallback_llm_api_key(self) -> str | None:
        """Valida el respaldo al arrancar (completo o nada); None si no hay respaldo."""
        provider = self.llm_fallback_provider
        if not provider:
            return None
        if provider not in PROVEEDORES_LLM:
            raise RuntimeError(
                f"LLM_FALLBACK_PROVIDER='{provider}' no es un proveedor conocido "
                f"({', '.join(sorted(PROVEEDORES_LLM))})."
            )
        if not self.llm_fallback_model:
            raise RuntimeError("LLM_FALLBACK_PROVIDER esta puesto pero falta LLM_FALLBACK_MODEL.")
        key = self._api_key_de(provider)
        if not key:
            raise RuntimeError(
                f"Falta {PROVEEDORES_LLM[provider]} para el modelo de respaldo "
                f"(LLM_FALLBACK_PROVIDER='{provider}')."
            )
        return key


settings = Settings()
