import re
from collections.abc import Mapping

BASE_SIGNAL_PATTERNS = {
    "asked_price": [
        r"\bprecio\b",
        r"\bcosto\b",
        r"\btarifa\b",
        r"\bcu[aá]nto cuesta\b",
        r"\bcu[aá]nto vale\b",
    ],
    "asked_availability": [
        r"\bdisponibilidad\b",
        r"\bhay lugar\b",
        r"\bhay espacio\b",
        r"\btienen horario\b",
        r"\btienen cita\b",
        r"\bhay cita\b",
    ],
    "asked_delivery": [
        r"\benv[ií]o\b",
        r"\bentrega\b",
        r"\bcu[aá]ndo llega\b",
        r"\bdomicilio\b",
    ],
    "asked_payment_methods": [
        r"\bpago\b",
        r"\bpagar\b",
        r"\btarjeta\b",
        r"\btransferencia\b",
        r"\befectivo\b",
        r"\bmeses sin intereses\b",
    ],
    "provided_preferred_date": [
        r"\bhoy\b",
        r"\bmañana\b",
        r"\bpasado mañana\b",
        r"\blunes\b",
        r"\bmartes\b",
        r"\bmi[eé]rcoles\b",
        r"\bjueves\b",
        r"\bviernes\b",
        r"\bs[aá]bado\b",
        r"\bdomingo\b",
        r"\b\d{1,2}/\d{1,2}\b",
        r"\b\d{1,2}-\d{1,2}\b",
    ],
    "provided_preferred_time": [
        r"\bmañana\b",
        r"\btarde\b",
        r"\bnoche\b",
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d{1,2}\s?(am|pm)\b",
    ],
    "clear_purchase_intent": [
        r"\bquiero agendar\b",
        r"\bquiero una cita\b",
        r"\bquiero comprar\b",
        r"\blo quiero\b",
        r"\bme interesa\b",
        r"\bapartarlo\b",
        r"\breservar\b",
        r"\bcontratar\b",
    ],
    "requested_human": [
        r"\basesor\b",
        r"\bpersona\b",
        r"\bhumano\b",
        r"\balguien me puede\b",
        r"\bhablar con alguien\b",
    ],
    "personalized_recommendation_needed": [
        r"\bme recomiendas\b",
        r"\bcu[aá]l me sirve\b",
        r"\bqu[eé] me conviene\b",
        r"\bpara mi caso\b",
    ],
    "complaint_or_problem": [
        r"\bqueja\b",
        r"\bno funcion[oó]\b",
        r"\btengo un problema\b",
        r"\bme fall[oó]\b",
        r"\bno lleg[oó]\b",
        r"\bno me respondieron\b",
    ],
}


def detect_text_signals(
    text: str,
    custom_patterns: Mapping[str, list[str]] | None = None,
) -> list[str]:
    normalized = text.lower()
    signals: list[str] = []
    signal_patterns = merge_signal_patterns(custom_patterns)

    for signal, patterns in signal_patterns.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            signals.append(signal)

    return signals


def merge_signal_patterns(
    custom_patterns: Mapping[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    signal_patterns = {
        signal: list(patterns)
        for signal, patterns in BASE_SIGNAL_PATTERNS.items()
    }

    if not custom_patterns:
        return signal_patterns

    for signal, patterns in custom_patterns.items():
        signal_patterns.setdefault(signal, []).extend(patterns)

    return signal_patterns
