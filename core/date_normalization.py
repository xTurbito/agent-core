"""Normalizacion deterministica de fechas relativas dichas por el usuario.

Interpretar "mañana" o "el sabado que viene" en el prompt es apostar: el LLM
no sabe que dia es hoy y calcula mal. Aqui se resuelve en Python puro contra
la zona horaria del negocio, y al modelo se le entrega ya la fecha ISO.
"""

import calendar
from dataclasses import asdict, dataclass
from dataclasses import replace as dataclasses_replace
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


_NOMBRES_DIA_SEMANA = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
)


def nombre_dia_semana(fecha: date) -> str:
    return _NOMBRES_DIA_SEMANA[fecha.weekday()]


@dataclass(frozen=True)
class DateInterpretation:
    status: str
    raw_text: str
    date: str | None
    interpretation: str
    needs_confirmation: bool
    reason: str | None = None
    weekday_name: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def business_zone() -> ZoneInfo:
    return ZoneInfo(settings.business_timezone)


def today_in_business_timezone() -> date:
    return datetime.now(business_zone()).date()


def months_between(start: date, end: date) -> int:
    """Meses de calendario completos entre dos fechas (no dias/30: un 6 de
    mayo a un 4 de noviembre son 6 meses, sin importar la duracion real de
    cada mes). Si end < start, regresa un numero negativo.

    El dia de start se compara contra el "aniversario" clampeado al ultimo
    dia real del mes de end, no contra end.day directo: sin esto, un 31 de
    enero a un 30 de junio (17 meses reales, el aniversario 31-jun no
    existe) contaba solo 16 y movia de rango cualquier calculo por meses."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    ultimo_dia_mes_destino = calendar.monthrange(end.year, end.month)[1]
    dia_aniversario = min(start.day, ultimo_dia_mes_destino)
    if end.day < dia_aniversario:
        months -= 1
    return months


def normalize_client_date(
    text: str,
    *,
    today: date | None = None,
) -> DateInterpretation | None:
    """Convierte una fecha dicha por el usuario a YYYY-MM-DD cuando es posible.

    Si el usuario tambien dijo un dia de la semana (ej. "el lunes 17 de
    noviembre"), ese nombre se ignora: weekday_name siempre es el dia real
    calculado en Python, porque el modelo etiquetaba fechas con el dia que el
    usuario dijo sin verificarlo."""
    interpretation = _normalize_client_date_inner(text, today=today)
    if interpretation is None or interpretation.date is None:
        return interpretation
    dia_real = nombre_dia_semana(date.fromisoformat(interpretation.date))
    return dataclasses_replace(interpretation, weekday_name=dia_real)


def _normalize_client_date_inner(
    text: str,
    *,
    today: date | None = None,
) -> DateInterpretation | None:
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
        # "del" solo con 4 digitos: "del 10 al 12" es un rango de dias, no el año 2010.
        rf"\b(\d{{1,2}})\s+de\s+({month_names})(?:\s+(?:de\s+(\d{{2,4}})|del\s+(\d{{4}})))?\b",
        text,
    )
    if not match:
        return None

    day = int(match.group(1))
    month = MONTHS[match.group(2)]
    raw_year = match.group(3) or match.group(4)
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
