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

    @property
    def active_llm_api_key(self) -> str | None:
        api_keys = {
            "google": self.google_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }
        return api_keys.get(self.llm_provider)


settings = Settings()
