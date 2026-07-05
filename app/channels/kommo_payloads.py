from typing import Any

from fastapi import Request


def parse_incoming_message(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "subdomain": payload.get("account[subdomain]"),
        "account_id": payload.get("account[id]"),
        "message_id": payload.get("message[add][0][id]"),
        "chat_id": payload.get("message[add][0][chat_id]"),
        "talk_id": payload.get("message[add][0][talk_id]"),
        "contact_id": payload.get("message[add][0][contact_id]"),
        "lead_id": payload.get("message[add][0][entity_id]"),
        "entity_type": payload.get("message[add][0][entity_type]"),
        "text": payload.get("message[add][0][text]"),
        "message_type": payload.get("message[add][0][message_type]"),
        "direction": payload.get("message[add][0][type]"),
        "author_type": payload.get("message[add][0][author][type]"),
        "author_name": payload.get("message[add][0][author][name]"),
        "origin": payload.get("message[add][0][origin]"),
        "created_at": payload.get("message[add][0][created_at]"),
    }


async def read_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        return await request.json()

    form = await request.form()
    return dict(form)


def pick_first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None
