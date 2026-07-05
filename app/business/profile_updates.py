from typing import Any

from app.business.qualification import calculate_qualification, should_handoff
from app.business.summarizer import summarize_conversation
from app.memory.profiles import (
    ConversationProfile,
    get_conversation_profile,
    update_conversation_profile,
)
from core.runner import AgentRunner


def apply_conversation_signals(
    *,
    runner: AgentRunner,
    session_id: str,
    signals: list[str],
    policy: str = "default",
    status: str | None = None,
    last_intent: str | None = None,
    summary: str | None = None,
    important_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConversationProfile | None:
    unique_signals = sorted(set(signals))

    qualification = calculate_qualification(unique_signals)
    handoff = should_handoff(unique_signals, qualification, policy)

    previous = get_conversation_profile(session_id)
    was_already_recommended = bool(previous and previous.handoff_recommended)
    just_triggered = handoff["handoff_recommended"] and not was_already_recommended

    if summary is None and just_triggered:
        summary = summarize_conversation(runner, session_id)

    merged_important_data = {
        "signals": unique_signals,
        **(important_data or {}),
    }

    merged_metadata = {
        "qualification_reason": qualification["qualification_reason"],
        "handoff_policy": policy,
        **(metadata or {}),
    }

    return update_conversation_profile(
        session_id=session_id,
        status=status,
        last_intent=last_intent,
        summary=summary,
        qualification_score=qualification["qualification_score"],
        qualification_label=qualification["qualification_label"],
        handoff_recommended=handoff["handoff_recommended"],
        handoff_reason=handoff["handoff_reason"],
        important_data=merged_important_data,
        metadata=merged_metadata,
    )
