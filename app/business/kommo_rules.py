from typing import Any

from app.integrations.kommo_client import kommo_config


def lead_has_paused_ai(lead: dict[str, Any]) -> bool:
    config = kommo_config()
    field_id = config.paused_field_id

    if not field_id:
        return False

    paused_values = {
        value.strip().lower()
        for value in config.paused_values.split(",")
        if value.strip()
    }

    for field in lead.get("custom_fields_values") or []:
        if str(field.get("field_id")) != str(field_id):
            continue

        for value in field.get("values") or []:
            raw_value = value.get("value")
            if str(raw_value).strip().lower() in paused_values:
                return True

    return False


def get_custom_field_values(lead: dict[str, Any], field_id: str | None) -> list[Any]:
    if not field_id:
        return []

    for field in lead.get("custom_fields_values") or []:
        if str(field.get("field_id")) == str(field_id):
            return [value.get("value") for value in field.get("values") or []]

    return []


def lead_is_allowed(lead_id: str | None) -> bool:
    config = kommo_config()
    raw_allowed = config.allowed_lead_ids

    if not raw_allowed:
        return True

    allowed = {value.strip() for value in raw_allowed.split(",") if value.strip()}
    return bool(lead_id) and str(lead_id) in allowed
