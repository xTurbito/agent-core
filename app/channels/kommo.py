import json
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.business.kommo_rules import (
    get_custom_field_values,
    lead_has_paused_ai,
    lead_is_allowed,
)
from app.business.custom_signal_patterns import CUSTOM_SIGNAL_PATTERNS
from app.business.profile_updates import apply_conversation_signals
from app.business.signal_detection import detect_text_signals
from app.channels.kommo_payloads import (
    parse_incoming_message,
    pick_first,
    read_payload,
)
from app.integrations.kommo_client import (
    continue_salesbot,
    get_kommo_lead,
    kommo_config,
    run_salesbot,
)
from app.memory.profiles import (
    get_or_create_contact_profile,
    get_or_create_conversation_profile,
)
from app.notifications import notify_error
from app.usage import log_usage
from core.runner import AgentRunner
from core.settings import settings

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

pending_ai_responses: dict[str, str] = {}


def ensure_kommo_profiles(event: dict[str, Any], session_id: str) -> None:
    try:
        contact = get_or_create_contact_profile(
            source="kommo",
            external_contact_id=(
                str(event["contact_id"]) if event.get("contact_id") else None
            ),
            name=event.get("author_name"),
            metadata={
                "account_id": event.get("account_id"),
                "subdomain": event.get("subdomain"),
                "chat_id": event.get("chat_id"),
                "talk_id": event.get("talk_id"),
                "origin": event.get("origin"),
                "author_type": event.get("author_type"),
            },
        )
        get_or_create_conversation_profile(
            source="kommo",
            external_conversation_id=(
                str(event["lead_id"]) if event.get("lead_id") else None
            ),
            contact_profile_id=contact.id,
            session_id=session_id,
            metadata={
                "account_id": event.get("account_id"),
                "subdomain": event.get("subdomain"),
                "message_id": event.get("message_id"),
                "chat_id": event.get("chat_id"),
                "talk_id": event.get("talk_id"),
                "contact_id": event.get("contact_id"),
                "origin": event.get("origin"),
            },
        )
    except Exception as exc:
        notify_error(
            exc,
            {
                "source": "kommo_profiles",
                "session_id": session_id,
                "lead_id": event.get("lead_id"),
                "contact_id": event.get("contact_id"),
            },
        )


def update_kommo_profile_signals(
    text: str, event: dict[str, Any], session_id: str, runner: AgentRunner
) -> None:
    try:
        signals = detect_text_signals(text, custom_patterns=CUSTOM_SIGNAL_PATTERNS)
        if not signals:
            return

        apply_conversation_signals(
            runner=runner,
            session_id=session_id,
            signals=signals,
            policy=settings.handoff_policy,
            metadata={
                "last_signal_source": "kommo_text",
                "last_message_id": event.get("message_id"),
            },
        )
    except Exception as exc:
        notify_error(
            exc,
            {
                "source": "kommo_signal_detection",
                "session_id": session_id,
                "lead_id": event.get("lead_id"),
                "message_id": event.get("message_id"),
            },
        )


def create_kommo_router(runner: AgentRunner) -> APIRouter:
    router = APIRouter(prefix="/kommo", tags=["kommo"])

    @router.get("/incoming-message")
    async def incoming_message_check() -> dict[str, str]:
        return {"status": "ok", "message": "Use POST for Kommo webhooks"}

    @router.post("/incoming-message")
    async def incoming_message(request: Request) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "")
        payload = await read_payload(request)

        event = parse_incoming_message(payload)

        print("KOMMO INCOMING MESSAGE:")
        print("content-type:", content_type)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        print("KOMMO PARSED EVENT:")
        print(json.dumps(event, ensure_ascii=False, indent=2))

        if event["direction"] != "incoming":
            return {"status": "ignored", "reason": "not incoming"}

        if event["entity_type"] != "lead":
            return {"status": "ignored", "reason": "not lead"}

        if event["message_type"] != "text":
            return {"status": "ignored", "reason": "not text"}

        if not event["lead_id"] or not event["text"]:
            return {"status": "ignored", "reason": "missing lead_id or text"}

        if not lead_is_allowed(event["lead_id"]):
            return {"status": "ignored", "reason": "lead not allowed"}

        try:
            lead = await get_kommo_lead(event["lead_id"])
        except (RuntimeError, httpx.HTTPError) as exc:
            print("KOMMO LEAD ERROR:", str(exc))
            return {"status": "error", "reason": "could not fetch lead"}

        print("KOMMO LEAD:")
        print(
            json.dumps(
                {
                    "id": lead.get("id"),
                    "name": lead.get("name"),
                    "status_id": lead.get("status_id"),
                    "pipeline_id": lead.get("pipeline_id"),
                    "has_custom_fields": bool(lead.get("custom_fields_values")),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        config = kommo_config()
        paused_field_values = get_custom_field_values(lead, config.paused_field_id)

        print("KOMMO AI PAUSED FIELD:")
        print(json.dumps(paused_field_values, ensure_ascii=False, indent=2))

        if lead_has_paused_ai(lead):
            return {"status": "ignored", "reason": "ai paused", "event": event}

        session_id = f"kommo-lead-{event['lead_id']}"
        ensure_kommo_profiles(event, session_id)
        started_at = perf_counter()

        try:
            result = await run_in_threadpool(
                runner.responder_con_metadata, session_id, event["text"]
            )
            respuesta = result["text"]
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)

            notify_error(
                exc,
                {
                    "source": "kommo_incoming_message",
                    "session_id": session_id,
                    "lead_id": event["lead_id"],
                    "message_id": event["message_id"],
                },
            )

            log_usage(
                {
                    "source": "kommo_incoming_message",
                    "session_id": session_id,
                    "lead_id": event["lead_id"],
                    "message_id": event["message_id"],
                    "status": "error",
                    "reason": "agent failed",
                    "message_length": len(event["text"]),
                    "latency_ms": latency_ms,
                }
            )

            return {
                "status": "error",
                "reason": "agent failed",
                "event": event,
            }

        print("AI RESPONSE:")
        print(respuesta)
        latency_ms = round((perf_counter() - started_at) * 1000)

        # Senales/handoff DESPUES de responder: asi el resumen incluye el mensaje
        # que disparo el handoff, y el LLM del resumen no bloquea el event loop.
        await run_in_threadpool(
            update_kommo_profile_signals, event["text"], event, session_id, runner
        )

        pending_ai_responses[str(event["lead_id"])] = respuesta

        log_usage(
            {
                "source": "kommo_incoming_message",
                "session_id": session_id,
                "lead_id": event["lead_id"],
                "message_id": event["message_id"],
                "status": "ok",
                "message_length": len(event["text"]),
                "response_length": len(respuesta),
                "latency_ms": latency_ms,
                "usage_metadata": result["usage_metadata"],
                "response_metadata": result["response_metadata"],
            }
        )

        try:
            await run_salesbot(str(event["lead_id"]))
        except (RuntimeError, httpx.HTTPError) as exc:
            print("KOMMO RUN SALESBOT ERROR:", str(exc))
            return {
                "status": "error",
                "reason": "could not run salesbot",
                "event": event,
                "respuesta": respuesta,
            }

        return {"status": "ok", "event": event, "respuesta": respuesta}

    @router.get("/widget-request")
    async def widget_request_check() -> dict[str, str]:
        return {"status": "ok", "message": "Use POST for Salesbot widget requests"}

    @router.post("/widget-request")
    async def widget_request(request: Request) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "")
        payload = await read_payload(request)

        print("KOMMO WIDGET REQUEST:")
        print("content-type:", content_type)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        message = pick_first(
            payload,
            "data[message]",
            "message",
            "text",
        )
        lead_id = pick_first(
            payload,
            "data[lead_id]",
            "lead_id",
            "entity_id",
        )
        return_url = pick_first(
            payload,
            "return_url",
            "data[return_url]",
        )

        if not lead_id:
            lead_id = "unknown"

        if not lead_is_allowed(str(lead_id)):
            return {"status": "ignored", "reason": "lead not allowed"}

        session_id = f"kommo-lead-{lead_id}"

        if lead_id != "unknown":
            widget_event = {
                "lead_id": lead_id,
                "contact_id": pick_first(payload, "data[contact_id]", "contact_id"),
                "account_id": None,
                "subdomain": None,
                "message_id": None,
                "chat_id": None,
                "talk_id": None,
                "origin": "widget_request",
                "author_name": None,
                "author_type": None,
            }
            ensure_kommo_profiles(widget_event, session_id)

        if not message:
            respuesta = pending_ai_responses.pop(str(lead_id), None)

            if not respuesta:
                return {"status": "ignored", "reason": "missing message"}

            print("WIDGET PENDING AI RESPONSE:")
            print(respuesta)

            if not return_url:
                return {
                    "status": "ok",
                    "reason": "missing return_url",
                    "respuesta": respuesta,
                }

            try:
                await continue_salesbot(str(return_url), respuesta)
            except (RuntimeError, httpx.HTTPError) as exc:
                print("KOMMO RETURN_URL ERROR:", str(exc))
                return {
                    "status": "error",
                    "reason": "could not continue salesbot",
                    "respuesta": respuesta,
                }

            return {"status": "ok", "respuesta": respuesta}

        started_at = perf_counter()

        try:
            result = await run_in_threadpool(
                runner.responder_con_metadata, session_id, str(message)
            )
            respuesta = result["text"]
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)

            notify_error(
                exc,
                {
                    "source": "kommo_widget_request",
                    "session_id": session_id,
                    "lead_id": lead_id,
                },
            )
            log_usage(
                {
                    "source": "kommo_widget_request",
                    "session_id": session_id,
                    "lead_id": lead_id,
                    "status": "error",
                    "reason": "agent failed",
                    "message_length": len(str(message)),
                    "latency_ms": latency_ms,
                }
            )
            return {
                "status": "error",
                "reason": "agent failed",
            }
        print("WIDGET AI RESPONSE:")
        print(respuesta)
        latency_ms = round((perf_counter() - started_at) * 1000)

        if lead_id != "unknown":
            await run_in_threadpool(
                update_kommo_profile_signals, str(message), widget_event, session_id, runner
            )

        log_usage(
            {
                "source": "kommo_widget_request",
                "session_id": session_id,
                "lead_id": lead_id,
                "status": "ok",
                "message_length": len(str(message)),
                "response_length": len(respuesta),
                "latency_ms": latency_ms,
                "usage_metadata": result["usage_metadata"],
                "response_metadata": result["response_metadata"],
            }
        )

        if not return_url:
            return {
                "status": "ok",
                "reason": "missing return_url",
                "respuesta": respuesta,
            }

        try:
            await continue_salesbot(str(return_url), respuesta)
        except httpx.HTTPError as exc:
            print("KOMMO RETURN_URL ERROR:", str(exc))
            return {
                "status": "error",
                "reason": "could not continue salesbot",
                "respuesta": respuesta,
            }

        return {"status": "ok", "respuesta": respuesta}

    return router
