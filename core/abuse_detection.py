"""Deteccion de abuso/spam en mensajes entrantes de leads.

No es moderacion de contenido general: es una defensa barata (sin LLM) contra
insultos directos al bot y intentos de jailbreak/prompt injection, para no
gastar tokens respondiendole a alguien que solo quiere romper el flujo.
"""

import re

INSULT_PATTERNS = [
    r"\bpendej[oa]\b",
    r"\bpinche\b",
    r"\bmierda\b",
    r"\bidiota\b",
    r"\bestupid[oa]\b",
    r"\bimb[eé]cil\b",
    r"\bputo\b",
    r"\bputa\b",
    r"\bverga\b",
    r"\bcabr[oó]n\b",
    r"\bfuck\b",
    r"\bshit\b",
    r"\bbitch\b",
]

JAILBREAK_PATTERNS = [
    r"\bignora( todas)? tus instrucciones\b",
    r"\bignora el prompt\b",
    r"\bolvida (todo lo anterior|tus instrucciones)\b",
    r"\bmuestra(me)? tu (system ?prompt|prompt del sistema)\b",
    r"\brevela tu(s)? instrucciones\b",
    r"\bactua como\b.{0,30}\b(sin restricciones|sin filtro|dan\b)",
    r"\bmodo desarrollador\b",
    r"\bdeveloper mode\b",
    r"\bjailbreak\b",
    r"\bignore (all )?(previous|prior) instructions\b",
]

# Mensajes de puro ruido (spam de caracteres repetidos, sin intencion real).
NOISE_PATTERN = re.compile(r"^(.)\1{9,}$")


def is_abusive_message(text: str) -> bool:
    """True si el mensaje trae insultos directos, intento de jailbreak o puro ruido."""
    normalized = text.lower().strip()

    if not normalized:
        return False

    if NOISE_PATTERN.match(normalized.replace(" ", "")):
        return True

    all_patterns = INSULT_PATTERNS + JAILBREAK_PATTERNS
    return any(re.search(pattern, normalized) for pattern in all_patterns)
