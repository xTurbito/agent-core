import os
from dataclasses import dataclass
from typing import Any

import httpx


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


async def continue_salesbot(return_url: str, text: str) -> None:
    config = kommo_config()

    if not config.access_token:
        raise RuntimeError("Missing KOMMO_ACCESS_TOKEN")

    body = {
        "data": {
            "status": "success",
            "message": text,
        },
        "execute_handlers": [
            {
                "handler": "show",
                "params": {
                    "type": "text",
                    "value": text,
                },
            }
        ],
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            return_url,
            json=body,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept": "application/json",
            },
        )
        print("KOMMO CONTINUE SALESBOT RESPONSE:")
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
