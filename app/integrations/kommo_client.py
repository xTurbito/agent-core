import json
import os
import re
from dataclasses import dataclass
from typing import Any
import unicodedata

import httpx

MAX_SHOW_VALUE_LENGTH = 80
# Kommo rechaza el request completo con 400 "TooMany" si execute_handlers trae
# mas de 10 elementos. Techo real de una respuesta: 10 bloques x 80 caracteres.
MAX_EXECUTE_HANDLERS = 10
KOMMO_EMOJI_REPLACEMENTS = {
    "😊": "☺",
    "🙂": "☺",
    "😄": "☺",
    "😁": "☺",
    "🥰": "✨",
    "😍": "✨",
    "💕": "✨",
    "💖": "✨",
    "❤️": "✨",
    "❤": "✨",
    "👋": "",
    "🙌": "✨",
    "✨": "✨",
}

# status_id reservados por Kommo: existen igual en TODAS las pipelines, no
# dependen de en cual este el lead. Los ids de etapas intermedias, en cambio,
# son de cada cuenta y viven en el fork.
KOMMO_LOST_STATUS_ID = 143
KOMMO_WIN_STATUS_ID = 142


@dataclass(frozen=True)
class KommoConfig:
    base_url: str | None
    access_token: str | None
    paused_field_id: str | None
    paused_values: str
    allowed_lead_ids: str | None
    salesbot_id: str | None


def kommo_config() -> KommoConfig:
    return KommoConfig(
        base_url=os.getenv("KOMMO_BASE_URL"),
        access_token=os.getenv("KOMMO_ACCESS_TOKEN"),
        paused_field_id=os.getenv("KOMMO_AI_PAUSED_FIELD_ID"),
        paused_values=os.getenv("KOMMO_AI_PAUSED_VALUES", "1,true,si,sí,yes"),
        allowed_lead_ids=os.getenv("KOMMO_ALLOWED_LEAD_IDS"),
        salesbot_id=os.getenv("KOMMO_SALESBOT_ID"),
    )


async def get_kommo_lead(lead_id: str) -> dict[str, Any]:
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/leads/{lead_id}"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {config.access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def get_kommo_contact(contact_id: str) -> dict[str, Any]:
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/contacts/{contact_id}"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {config.access_token}"},
        )
        response.raise_for_status()
        return response.json()


def extract_contact_phone(contact: dict[str, Any]) -> str | None:
    """Primer telefono del contacto (custom field PHONE de Kommo)."""
    for field in contact.get("custom_fields_values") or []:
        if field.get("field_code") != "PHONE":
            continue
        for value in field.get("values") or []:
            phone = str(value.get("value") or "").strip()
            if phone:
                return phone
    return None


async def continue_salesbot(return_url: str, text: str) -> None:
    config = kommo_config()

    if not config.access_token:
        raise RuntimeError("Missing KOMMO_ACCESS_TOKEN")

    kommo_text = adapt_text_for_kommo(text)
    print("KOMMO ADAPTED RESPONSE:")
    print(kommo_text)

    execute_handlers = build_show_handlers(kommo_text)

    body = build_continue_salesbot_body(kommo_text, execute_handlers)
    encoded_body = encode_json_utf8(body)

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            return_url,
            content=encoded_body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        print("KOMMO CONTINUE SALESBOT RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()


def build_continue_salesbot_body(
    text: str,
    execute_handlers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "data": {
            "status": "success",
            "message": text,
        },
        "execute_handlers": execute_handlers,
    }


def encode_json_utf8(body: dict[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def adapt_text_for_kommo(text: str) -> str:
    """Convierte emojis que WABA/Salesbot suele degradar a simbolos seguros.

    Colapsa espacios/tabs sueltos pero conserva los saltos de linea: sin eso,
    una lista con vinetas del LLM llega a WhatsApp como un solo parrafo
    aplastado.
    """
    adapted = text
    for original, replacement in KOMMO_EMOJI_REPLACEMENTS.items():
        adapted = adapted.replace(original, replacement)
    adapted = strip_remaining_modern_emojis(adapted)
    # el prompt pide asterisco simple para negritas, pero el LLM a veces cae
    # en markdown estandar (**texto**); WhatsApp no lo renderiza y se ve
    # literal con los asteriscos.
    adapted = re.sub(r"\*\*(.+?)\*\*", r"*\1*", adapted)
    lines = [" ".join(line.split()) for line in adapted.splitlines()]
    return "\n".join(line for line in lines if line)


def strip_remaining_modern_emojis(text: str) -> str:
    """Quita caracteres fuera del BMP que algunos puentes WABA vuelven '?'."""
    safe_chars = []
    for char in text:
        if ord(char) > 0xFFFF:
            continue
        if unicodedata.category(char) == "Cs":
            continue
        safe_chars.append(char)
    return "".join(safe_chars)


def build_show_handlers(text: str) -> list[dict[str, Any]]:
    """Arma los handlers "show" respetando los DOS limites de Kommo.

    Kommo limita cada handler a 80 caracteres y ademas la coleccion completa a
    10 handlers. Como split_show_text trocea linea por linea, una lista con una
    opcion por renglon gasta un handler por renglon y revienta el segundo limite
    con textos cortos: la llamada regresa 400 y el lead NO recibe nada.

    Por eso, cuando un bubble por renglon (lo bonito en WhatsApp) no cabe, se
    juntan renglones en bloques de 80 para ganar lugar.

    A proposito NO se recorta el texto si ni compactado cabe: pasar de 800
    caracteres significa que el prompt dejo al agente soltar una parrafada que
    no deberia, y eso se arregla en el prompt (o reintentando comprimido, ver
    docs). Recortando se taparia el bug y el lead leeria media respuesta;
    mejor que truene y se vea en el log.
    """
    chunks = split_show_text(text)

    if len(chunks) > MAX_EXECUTE_HANDLERS:
        print(
            "KOMMO SHOW OVERFLOW: "
            f"{len(chunks)} bloques por renglon, compactando a {MAX_EXECUTE_HANDLERS}"
        )
        chunks = _chunk_line(" ".join(text.split()), MAX_SHOW_VALUE_LENGTH)

    return [
        {
            "handler": "show",
            "params": {
                "type": "text",
                "value": chunk,
            },
        }
        for chunk in chunks
    ]


def split_show_text(text: str, limit: int = MAX_SHOW_VALUE_LENGTH) -> list[str]:
    """Kommo limita cada handler show a 80 caracteres.

    Cada chunk se manda como su propio mensaje/bubble en WhatsApp, asi que un
    salto de linea del texto original nunca se junta con la siguiente linea
    en el mismo chunk (por eso se trocea linea por linea, no el texto entero).
    """
    chunks: list[str] = []

    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            chunks.extend(_chunk_line(line, limit))

    return chunks


def _chunk_line(line: str, limit: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for word in line.split(" "):
        if len(word) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(word[index : index + limit] for index in range(0, len(word), limit))
            continue

        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
            continue

        chunks.append(current)
        current = word

    if current:
        chunks.append(current)

    return chunks


async def pause_lead_ai(lead_id: str) -> None:
    """Marca el lead como IA pausada usando el mismo campo que lead_has_paused_ai.

    Se usa cuando se detecta abuso/spam: en vez de que el equipo pause al
    lead a mano en Kommo, el bot lo marca solo y deja de responderle.
    """
    config = kommo_config()

    if not config.base_url or not config.access_token or not config.paused_field_id:
        raise RuntimeError(
            "Missing KOMMO_BASE_URL, KOMMO_ACCESS_TOKEN or KOMMO_AI_PAUSED_FIELD_ID"
        )

    url = f"{config.base_url.rstrip('/')}/api/v4/leads/{lead_id}"
    body = {
        "custom_fields_values": [
            {
                "field_id": int(config.paused_field_id),
                # Campo tipo checkbox en Kommo: exige bool, no el string de
                # KOMMO_AI_PAUSED_VALUES (ese solo se usa para *leer*).
                "values": [{"value": True}],
            }
        ]
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.patch(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO PAUSE LEAD RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()


async def update_lead_custom_fields(lead_id: str, fields: list[dict]) -> None:
    """Actualiza custom fields arbitrarios de un lead.

    fields: lista de {"field_id": int, "value": Any} para texto/fecha/checkbox,
    o {"field_id": int, "enum_id": int} para campos tipo select (Kommo exige
    enum_id ahi, "value" con el id numerico lo rechaza con 400). Un solo
    PATCH para todos los campos del turno, nunca uno por campo.
    """
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/leads/{lead_id}"
    body = {
        "custom_fields_values": [
            {
                "field_id": f["field_id"],
                "values": [
                    {"enum_id": f["enum_id"]} if "enum_id" in f else {"value": f["value"]}
                ],
            }
            for f in fields
        ]
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.patch(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO UPDATE CUSTOM FIELDS RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()


async def mark_lead_lost(lead_id: str, loss_reason_id: int) -> None:
    """Cierra el lead como Lost con una razon real, para reportes en Kommo.

    Se usa cuando el bot detecta que el lead no califica, en vez de dejarlo
    indefinidamente en el pipeline sin resolver. El catalogo de
    loss_reason_id es de cada cuenta (GET /api/v4/leads/loss_reasons) y vive
    en el fork, no aqui.
    """
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/leads/{lead_id}"
    body = {"status_id": KOMMO_LOST_STATUS_ID, "loss_reason_id": loss_reason_id}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.patch(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO MARK LOST RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()


async def move_lead_stage(lead_id: str, status_id: int) -> None:
    """Mueve el lead a otra etapa DENTRO de su pipeline actual (no toca Lost/Win)."""
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/leads/{lead_id}"
    body = {"status_id": status_id}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.patch(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO MOVE STAGE RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()


async def search_kommo_contact_by_phone(telefono: str) -> dict | None:
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/contacts"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            url,
            params={"query": telefono, "limit": 1},
            headers={"Authorization": f"Bearer {config.access_token}"},
        )
        response.raise_for_status()
        # Kommo regresa 204 sin body cuando no hay coincidencias (no un
        # array vacio); .json() tronaria con JSONDecodeError.
        if response.status_code == 204 or not response.content:
            return None
        contactos = response.json().get("_embedded", {}).get("contacts", [])
        return contactos[0] if contactos else None


async def link_contact_to_lead(lead_id: str, contact_id: str) -> None:
    config = kommo_config()

    if not config.base_url or not config.access_token:
        raise RuntimeError("Missing KOMMO_BASE_URL or KOMMO_ACCESS_TOKEN")

    url = f"{config.base_url.rstrip('/')}/api/v4/leads/{lead_id}/link"
    body = [{"to_entity_id": int(contact_id), "to_entity_type": "contacts"}]

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO LINK CONTACT RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()


async def run_salesbot(lead_id: str) -> None:
    config = kommo_config()

    if (
        not config.base_url
        or not config.access_token
        or not config.salesbot_id
    ):
        raise RuntimeError(
            "Missing KOMMO_BASE_URL, KOMMO_ACCESS_TOKEN or KOMMO_SALESBOT_ID"
        )

    url = f"{config.base_url.rstrip('/')}/api/v4/bots/{config.salesbot_id}/run"
    entity_id: int | str = int(lead_id) if str(lead_id).isdigit() else lead_id
    body = {
        "entity_id": entity_id,
        "entity_type": "leads",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO RUN SALESBOT RESPONSE:")
        print("status:", response.status_code)
        print("body:", response.text)
        response.raise_for_status()
