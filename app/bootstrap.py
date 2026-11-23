"""Arma el runner de ESTE cliente (fork).

Junta config (settings) + tools del negocio + prompt, y devuelve un
AgentRunner listo. El core no sabe de esto; es especifico del fork.
"""

from app.memory.context import build_business_context
from app.prompts.system import SYSTEM_PROMPT
from app.tools.disponibilidad import consultar_disponibilidad
from core.agent import build_agent
from core.llm import make_llm
from core.memory import make_checkpointer
from core.runner import AgentRunner
from core.settings import settings

TOOLS = [consultar_disponibilidad]


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


def build_runner() -> AgentRunner:
    llm, llm_respaldo = construir_llms()
    checkpointer = make_checkpointer(settings.memory_kind)
    agent = build_agent(
        llm,
        TOOLS,
        SYSTEM_PROMPT,
        checkpointer=checkpointer,
        context_provider=build_business_context,
        llm_respaldo=llm_respaldo,
    )
    return AgentRunner(agent)
