"""Arma el runner de ESTE cliente (fork).

Junta config (settings) + tools del negocio + prompt, y devuelve un
AgentRunner listo. El core no sabe de esto; es especifico del fork.
"""

from core.settings import settings
from core.llm import make_llm
from core.memory import make_checkpointer
from core.agent import build_agent
from core.runner import AgentRunner

from app.tools.disponibilidad import consultar_disponibilidad


SYSTEM_PROMPT = (
    "Eres el asistente de una clinica dental. "
    "Responde en espanol, breve y amable. "
    "Usa las tools para datos reales. NUNCA inventes disponibilidad."
)

TOOLS = [consultar_disponibilidad]

# Cada proveedor usa su propia key del .env
API_KEYS = {
    "google": settings.google_api_key,
    "anthropic": settings.anthropic_api_key,
    "openai": settings.openai_api_key,
}


def build_runner() -> AgentRunner:
    llm = make_llm(
        settings.llm_provider,
        settings.llm_model,
        api_key=API_KEYS[settings.llm_provider],
    )
    checkpointer = make_checkpointer(settings.memory_kind)
    agent = build_agent(llm, TOOLS, SYSTEM_PROMPT, checkpointer=checkpointer)
    return AgentRunner(agent)