"""Settings del bot, leidos del .env y validados.

Una sola fuente de verdad para la config. Cambias el .env -> cambias
el comportamiento, sin tocar codigo. Cada fork tiene su propio .env.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # proveedor del LLM
    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"

    # tipo de memoria
    memory_kind: str = "memory"
    postgres_url: str | None = None

    # API keys (opcionales; usas la del provider elegido)
    google_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

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

    @property
    def active_llm_api_key(self) -> str | None:
        api_keys = {
            "google": self.google_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }
        return api_keys.get(self.llm_provider)

    def require_llm_api_key(self) -> str:
        """Fail-fast al arrancar: mejor tronar aqui que a medio request.

        Se llama desde el bootstrap del servidor, no al importar, para que
        los tests puros (sin .env) sigan corriendo.
        """
        key = self.active_llm_api_key
        if not key:
            raise RuntimeError(
                f"Falta la API key para el provider '{self.llm_provider}'. "
                "Revisa el .env (GOOGLE_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY)."
            )
        return key


settings = Settings()
