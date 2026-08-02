"""Factory de LLM.

Devuelve un chat model segun el proveedor elegido en config.
Todos los proveedores exponen la MISMA interfaz de LangChain,
asi el agente, webhook y tools nunca cambian al cambiar de LLM.
"""

# Sin timeout, una llamada colgada al proveedor cuelga el lock por-sesion de
# AgentRunner para SIEMPRE (visto en pruebas de carga: una sesion se quedo
# atorada indefinidamente bajo 8 sesiones concurrentes). Cada proveedor de
# LangChain acepta "timeout" y lo aplica al cliente HTTP subyacente.
DEFAULT_TIMEOUT_SECONDS = 30


def make_llm(provider: str = "google", model: str = "gemini-2.5-flash", api_key=None, **kwargs):
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT_SECONDS)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key, **kwargs)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key, **kwargs)

    raise ValueError(f"Proveedor LLM no soportado: {provider}")
