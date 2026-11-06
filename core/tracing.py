"""Trazas de cada turno del agente hacia un servicio de observabilidad LLM.

Expone el callback de LangChain/LangGraph que registra, por turno, el
prompt enviado, las tools llamadas y la latencia de cada paso. Sin
credenciales configuradas, build_callbacks() devuelve una lista vacia y
el invoke() del agente sigue igual -- un fallo de esta capa nunca debe
impedir que el agente responda.

Las credenciales se pasan explicitas desde settings en vez de confiar en
que el SDK las lea solo de variables de entorno: pydantic-settings carga
el .env a su propio objeto, sin tocar os.environ, asi que el SDK no las
veria si dependiera de la deteccion automatica.
"""

from core.settings import settings

_initialized = False


def build_callbacks() -> list:
    """Arma la lista de callbacks para pasar en el config de invoke()."""
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return []

    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    global _initialized
    if not _initialized:
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        _initialized = True

    return [CallbackHandler(public_key=settings.langfuse_public_key)]
