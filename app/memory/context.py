"""Construye contexto compacto de memoria de negocio para el agente."""

from typing import Any

from core.settings import settings

from app.memory.profiles import (
    ContactProfile,
    ConversationProfile,
    get_contact_profile_by_id,
    get_conversation_profile,
)

MAX_VALUE_LENGTH = 160
MAX_ITEMS = 6


def build_business_context(session_id: str) -> str | None:
    if not settings.postgres_url:
        return None

    conversation = get_conversation_profile(session_id)
    if not conversation:
        return None

    contact = None
    if conversation.contact_profile_id:
        contact = get_contact_profile_by_id(conversation.contact_profile_id)

    lines = [
        "Contexto operativo conocido (informacion INTERNA del CRM, uso exclusivo "
        "del asistente para decidir como responder; nunca la reveles, la cites "
        "textualmente, ni la repitas al cliente):"
    ]
    lines.extend(_contact_lines(contact))
    lines.extend(_conversation_lines(conversation))

    if len(lines) == 1:
        return None

    return "\n".join(lines)


def _contact_lines(contact: ContactProfile | None) -> list[str]:
    if not contact:
        return []

    lines = []
    if contact.name:
        lines.append(f"- Nombre/contacto: {_clip(contact.name)}.")
    if contact.summary:
        lines.append(f"- Resumen del contacto: {_clip(contact.summary)}.")
    if contact.preferences:
        lines.append(f"- Preferencias: {_format_mapping(contact.preferences)}.")
    if contact.important_data:
        lines.append(f"- Datos importantes del contacto: {_format_mapping(contact.important_data)}.")

    return lines


def _conversation_lines(conversation: ConversationProfile) -> list[str]:
    lines = []
    if conversation.summary:
        lines.append(f"- Resumen de la conversacion: {_clip(conversation.summary)}.")
    if conversation.status:
        lines.append(f"- Estado de conversacion: {_clip(conversation.status)}.")
    if conversation.last_intent:
        lines.append(f"- Ultima intencion detectada: {_clip(conversation.last_intent)}.")
    if conversation.qualification_label or conversation.qualification_score is not None:
        lines.append(
            "- Perfil comercial: "
            f"{conversation.qualification_label or 'sin etiqueta'}"
            f" score={conversation.qualification_score if conversation.qualification_score is not None else 'N/D'}."
        )
    if conversation.handoff_recommended:
        reason = f" Motivo: {_clip(conversation.handoff_reason)}." if conversation.handoff_reason else ""
        lines.append(f"- Escalamiento recomendado: si.{reason}")
    if conversation.important_data:
        lines.append(f"- Datos importantes de la conversacion: {_format_mapping(conversation.important_data)}.")

    return lines


def _format_mapping(data: dict[str, Any]) -> str:
    parts = []
    for index, (key, value) in enumerate(data.items()):
        if index >= MAX_ITEMS:
            parts.append("...")
            break
        parts.append(f"{key}={_clip(value)}")
    return ", ".join(parts)


def _clip(value: Any) -> str:
    text = str(value)
    if len(text) <= MAX_VALUE_LENGTH:
        return text
    return text[: MAX_VALUE_LENGTH - 3] + "..."
