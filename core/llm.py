"""Factory de LLM.

Devuelve un chat model segun el proveedor elegido en config.
Todos los proveedores exponen la MISMA interfaz de LangChain,
asi el agente, webhook y tools nunca cambian al cambiar de LLM.
"""

import logging

from core.runner import extract_text
from core.settings import settings

logger = logging.getLogger(__name__)

# Sin timeout, una llamada colgada al proveedor cuelga el lock por-sesion de
# AgentRunner para SIEMPRE (visto en pruebas de carga: una sesion se quedo
# atorada indefinidamente bajo 8 sesiones concurrentes). Cada proveedor de
# LangChain acepta "timeout" y lo aplica al cliente HTTP subyacente.
DEFAULT_TIMEOUT_SECONDS = 30

# Sin max_tokens, ChatOpenAI (openai/openrouter) pide la ventana de contexto completa como limite
# de salida y OpenRouter rechaza la llamada con 402 si el saldo no alcanza. El tope tambien cuenta
# el razonamiento del modelo: con 2048 algunas respuestas salian cortadas. 4096 deja margen.
DEFAULT_MAX_TOKENS = 4096


def make_llm(
    provider: str = "google",
    model: str = "gemini-2.5-flash",
    api_key=None,
    reasoning_effort: str | None = None,
    **kwargs,
):
    """Arma el chat model del proveedor; reasoning_effort solo aplica a openai y openrouter."""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT_SECONDS)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key, **kwargs)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        kwargs.setdefault("max_tokens", DEFAULT_MAX_TOKENS)
        return ChatOpenAI(model=model, api_key=api_key, **kwargs)

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        kwargs.setdefault("max_tokens", DEFAULT_MAX_TOKENS)
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            **kwargs,
        )

    raise ValueError(f"Proveedor LLM no soportado: {provider}")


def construir_llms() -> tuple:
    """Devuelve (llm, llm_respaldo); el respaldo es None si no esta configurado."""
    key_respaldo = settings.require_fallback_llm_api_key()
    # Con respaldo, el primario falla a la primera en vez de reintentar hasta el timeout.
    extras = {"max_retries": 0} if key_respaldo else {}
    llm = make_llm(
        settings.llm_provider,
        settings.llm_model,
        api_key=settings.require_llm_api_key(),
        reasoning_effort=settings.llm_reasoning_effort,
        **extras,
    )
    llm_respaldo = None
    # require_fallback_llm_api_key ya valido proveedor y modelo; esto solo lo hace visible a mypy.
    if key_respaldo and settings.llm_fallback_provider and settings.llm_fallback_model:
        llm_respaldo = make_llm(
            settings.llm_fallback_provider,
            settings.llm_fallback_model,
            api_key=key_respaldo,
            reasoning_effort=settings.llm_fallback_reasoning_effort,
        )
    return llm, llm_respaldo


def invocar_con_respaldo(entrada, llm, respaldo=None):
    """Llamada suelta al LLM con la misma red que el agente: si el primario falla, el respaldo."""
    try:
        respuesta = llm.invoke(entrada)
    except Exception as exc:
        if respaldo is None:
            raise
        logger.warning(
            "LLM primario fallo en llamada suelta (%s); se usa el respaldo", type(exc).__name__
        )
        return respaldo.invoke(entrada)
    if respaldo is not None and not extract_text(respuesta.content).strip():
        logger.warning("LLM primario regreso vacio en llamada suelta; se usa el respaldo")
        return respaldo.invoke(entrada)
    return respuesta
