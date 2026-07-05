"""Genera un resumen corto de la conversacion para que un humano retome el hilo."""

from langchain_core.messages import AIMessage, HumanMessage

from core.llm import make_llm
from core.runner import AgentRunner, extract_text
from core.settings import settings

SUMMARY_PROMPT = (
    "Resume la siguiente conversacion entre un cliente y un asistente de negocio. "
    "El resumen es para que un asesor humano retome la conversacion sin leer todo el "
    "historial. En 3-4 lineas: que quiere el cliente, datos importantes que dio "
    "(nombre, telefono, fechas, presupuesto, etc.) y en que quedo la conversacion. "
    "No agregues nada que no este en la conversacion.\n\n"
    "Conversacion:\n{transcript}"
)


def summarize_conversation(runner: AgentRunner, session_id: str) -> str | None:
    messages = runner.get_conversation_messages(session_id)
    if not messages:
        return None

    transcript = _format_transcript(messages)
    if not transcript:
        return None

    llm = make_llm(settings.llm_provider, settings.llm_model, api_key=settings.active_llm_api_key)
    response = llm.invoke(SUMMARY_PROMPT.format(transcript=transcript))
    return extract_text(response.content)


def _format_transcript(messages: list) -> str:
    lines = []
    for message in messages:
        if isinstance(message, HumanMessage):
            lines.append(f"Cliente: {extract_text(message.content)}")
        elif isinstance(message, AIMessage):
            lines.append(f"Asistente: {extract_text(message.content)}")
    return "\n".join(lines)
