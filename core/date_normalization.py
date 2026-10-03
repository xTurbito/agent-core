"""Normalizacion deterministica de fechas relativas dichas por el usuario.

Interpretar "mañana" o "el sabado que viene" en el prompt es apostar: el LLM
no sabe que dia es hoy y calcula mal. Aqui se resuelve en Python puro contra
la zona horaria del negocio, y al modelo se le entrega ya la fecha ISO.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import re
import unicodedata
from zoneinfo import ZoneInfo

from core.settings import settings

WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

AMBIGUOUS_RELATIVE_RE = re.compile(
    r"\b(el|la)?\s*(que viene|proxim[oa]|siguiente)\b"
    r"|\b(la otra semana|proxima semana|siguiente semana)\b"
)


@dataclass(frozen=True)
class DateInterpretation:
    status: str
    raw_text: str
    date: str | None
    interpretation: str
    needs_confirmation: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def today_in_business_timezone() -> date:
    return datetime.now(ZoneInfo(settings.business_timezone)).date()


def normalize_client_date(
    text: str,
    *,
    today: date | None = None,
) -> DateInterpretation | None:
    """Convierte una fecha dicha por el usuario a YYYY-MM-DD cuando es posible."""
    reference = today or today_in_business_timezone()
    normalized = _normalize_text(text)

    numeric = _parse_numeric_date(normalized, reference)
    if numeric:
        raw, parsed = numeric
        return DateInterpretation(
            status="confirmed",
            raw_text=raw,
            date=parsed.isoformat(),
            interpretation=f"Fecha explicita interpretada como {parsed.isoformat()}",
            needs_confirmation=False,
        )

    month_name = _parse_month_name_date(normalized, reference)
    if month_name:
        raw, parsed = month_name
        return DateInterpretation(
            status="confirmed",
            raw_text=raw,
            date=parsed.isoformat(),
            interpretation=f"Fecha explicita interpretada como {parsed.isoformat()}",
            needs_confirmation=False,
        )

    if re.search(r"\bpasado\s+manana\b", normalized):
        parsed = reference + timedelta(days=2)
        return DateInterpretation(
            status="confirmed",
            raw_text="pasado manana",
            date=parsed.isoformat(),
            interpretation="pasado manana",
            needs_confirmation=False,
        )

    if _mentions_tomorrow_as_date(normalized):
        parsed = reference + timedelta(days=1)
        return DateInterpretation(
            status="confirmed",
            raw_text="manana",
            date=parsed.isoformat(),
            interpretation="manana",
            needs_confirmation=False,
        )

    if re.search(r"\bhoy\b", normalized):
        return DateInterpretation(
            status="confirmed",
            raw_text="hoy",
            date=reference.isoformat(),
            interpretation="hoy",
            needs_confirmation=False,
        )

    weekday = _parse_weekday(normalized, reference)
    if weekday:
        return weekday

    ambiguous = AMBIGUOUS_RELATIVE_RE.search(normalized)
    if ambiguous:
        raw = ambiguous.group(0).strip()
        return DateInterpretation(
            status="ambiguous",
            raw_text=raw,
            date=None,
            interpretation=raw,
            needs_confirmation=True,
            reason=(
                "La frase relativa no incluye dia concreto suficiente para "
                "convertirla a una fecha."
            ),
        )

    return None


def _parse_weekday(text: str, reference: date) -> DateInterpretation | None:
    for name, weekday in WEEKDAYS.items():
        if not re.search(rf"\b{name}\b", text):
            continue

        relative_match = re.search(
            rf"\b(este|esta|proximo|proxima|siguiente)\s+{name}\b"
            rf"|\b{name}\s+(que viene|proximo|proxima|siguiente)\b",
            text,
        )
        raw_text = relative_match.group(0) if relative_match else name
        has_relative_marker = bool(relative_match)
        parsed = _next_weekday(reference, weekday)

        return DateInterpretation(
            status="confirmed",
            raw_text=raw_text,
            date=parsed.isoformat(),
            interpretation=f"{raw_text} interpretado como {parsed.isoformat()}",
            needs_confirmation=False,
        )

    return None


def _parse_numeric_date(text: str, reference: date) -> tuple[str, date] | None:
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text)
    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    raw_year = match.group(3)
    year = _normalize_year(raw_year) if raw_year else reference.year

    try:
        parsed = date(year, month, day)
    except ValueError:
        return None

    if not raw_year and parsed < reference:
        parsed = date(reference.year + 1, month, day)

    return match.group(0), parsed


def _parse_month_name_date(text: str, reference: date) -> tuple[str, date] | None:
    month_names = "|".join(MONTHS)
    match = re.search(
        rf"\b(\d{{1,2}})\s+de\s+({month_names})(?:\s+de\s+(\d{{2,4}}))?\b",
        text,
    )
    if not match:
        return None

    day = int(match.group(1))
    month = MONTHS[match.group(2)]
    raw_year = match.group(3)
    year = _normalize_year(raw_year) if raw_year else reference.year

    try:
        parsed = date(year, month, day)
    except ValueError:
        return None

    if not raw_year and parsed < reference:
        parsed = date(reference.year + 1, month, day)

    return match.group(0), parsed


def _next_weekday(reference: date, weekday: int) -> date:
    days_ahead = (weekday - reference.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return reference + timedelta(days=days_ahead)


def _mentions_tomorrow_as_date(text: str) -> bool:
    without_time_phrase = re.sub(r"\b(en|por|de)\s+la\s+manana\b", "", text)
    return bool(re.search(r"\bmanana\b", without_time_phrase))


def _normalize_year(raw_year: str | None) -> int:
    if not raw_year:
        raise ValueError("raw_year requerido")

    year = int(raw_year)
    if year < 100:
        return 2000 + year
    return year


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_accents).strip()
