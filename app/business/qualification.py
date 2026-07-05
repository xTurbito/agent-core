SIGNAL_WEIGHTS = {
    "asked_price": 10,
    "asked_availability": 15,
    "asked_delivery": 10,
    "provided_name": 10,
    "provided_phone": 15,
    "provided_email": 10,
    "provided_preferred_date": 15,
    "provided_preferred_time": 10,
    "selected_product_or_service": 20,
    "asked_payment_methods": 10,
    "requested_human": 30,
    "clear_purchase_intent": 30,
    "booking_confirmed": 100,
    "purchase_completed": 100,
}

HANDOFF_POLICIES = {
    "default": {
        "score_threshold": 80,
        "always_handoff_signals": {
            "requested_human",
            "technical_error",
        },
    },
    "appointment_agent": {
        "score_threshold": 100,
        "always_handoff_signals": {
            "requested_human",
            "technical_error",
            "sensitive_case",
            "medical_or_health_question",
            "personalized_recommendation_needed",
            "complex_service_fit_question",
            "complaint_or_adverse_reaction",
            "high_risk_claim",
            "complex_reschedule",
        },
    },
    "sales_agent": {
        "score_threshold": 80,
        "always_handoff_signals": {
            "requested_human",
            "technical_error",
            "high_value_opportunity",
            "strong_objection",
            "complaint_or_adverse_reaction",
        },
    },
}


def calculate_qualification(signals: list[str]) -> dict:
    score = min(sum(SIGNAL_WEIGHTS.get(signal, 0) for signal in set(signals)), 100)

    if score >= 80:
        label = "hot"
    elif score >= 50:
        label = "warm"
    elif score > 0:
        label = "cold"
    else:
        label = "unknown"

    return {
        "qualification_score": score,
        "qualification_label": label,
        "qualification_reason": build_qualification_reason(signals, score, label),
    }


def should_handoff(
    signals: list[str],
    qualification: dict,
    policy: str = "default",
) -> dict:
    selected_policy = HANDOFF_POLICIES.get(policy, HANDOFF_POLICIES["default"])
    unique_signals = set(signals)
    forced_signals = unique_signals & selected_policy["always_handoff_signals"]
    score = qualification["qualification_score"]
    score_threshold = selected_policy["score_threshold"]

    handoff_recommended = bool(forced_signals) or score >= score_threshold

    return {
        "handoff_recommended": handoff_recommended,
        "handoff_reason": build_handoff_reason(
            signals=signals,
            score=score,
            label=qualification["qualification_label"],
            policy=policy,
            forced_signals=forced_signals,
            score_threshold=score_threshold,
        ),
    }


def build_qualification_reason(signals: list[str], score: int, label: str) -> str | None:
    if not signals:
        return None

    return f"Lead {label} con score {score}. Señales detectadas: {', '.join(sorted(set(signals)))}."


def build_handoff_reason(
    *,
    signals: list[str],
    score: int,
    label: str,
    policy: str,
    forced_signals: set[str],
    score_threshold: int,
) -> str | None:
    if forced_signals:
        return (
            f"Escalamiento recomendado por politica {policy}. "
            f"Señales de escalamiento: {', '.join(sorted(forced_signals))}."
        )

    if score >= score_threshold:
        return (
            f"Escalamiento recomendado por score comercial. "
            f"Lead {label} con score {score}. "
            f"Señales detectadas: {', '.join(sorted(set(signals)))}."
        )

    return None
