import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

load_dotenv()

LOG_PATH = Path("logs/usage.jsonl")

STRUCTURED_KEYS = {
    "source",
    "session_id",
    "external_contact_id",
    "external_conversation_id",
    "lead_id",
    "status",
    "reason",
    "message_length",
    "response_length",
    "latency_ms",
    "usage_metadata",
    "response_metadata",
}


def log_usage(event: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": time.time(),
        **event,
    }

    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    try:
        log_usage_to_postgres(event)
    except Exception as exc:
        print("USAGE LOG POSTGRES ERROR:", str(exc))


def log_usage_to_postgres(event: dict[str, Any]) -> None:
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        return

    metadata = {
        key: value
        for key, value in event.items()
        if key not in STRUCTURED_KEYS
    }

    with psycopg.connect(postgres_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usage_logs (
                    timestamp,
                    source,
                    session_id,
                    external_contact_id,
                    external_conversation_id,
                    status,
                    reason,
                    message_length,
                    response_length,
                    latency_ms,
                    usage_metadata,
                    response_metadata,
                    metadata
                )
                VALUES (
                    %(timestamp)s,
                    %(source)s,
                    %(session_id)s,
                    %(external_contact_id)s,
                    %(external_conversation_id)s,
                    %(status)s,
                    %(reason)s,
                    %(message_length)s,
                    %(response_length)s,
                    %(latency_ms)s,
                    %(usage_metadata)s,
                    %(response_metadata)s,
                    %(metadata)s
                )
                """,
                {
                    "timestamp": datetime.now(timezone.utc),
                    "source": event.get("source", "unknown"),
                    "session_id": event.get("session_id"),
                    "external_contact_id": event.get("external_contact_id"),
                    "external_conversation_id": event.get("external_conversation_id")
                    or event.get("lead_id"),
                    "status": event.get("status"),
                    "reason": event.get("reason"),
                    "message_length": event.get("message_length"),
                    "response_length": event.get("response_length"),
                    "latency_ms": event.get("latency_ms"),
                    "usage_metadata": Jsonb(event.get("usage_metadata")),
                    "response_metadata": Jsonb(event.get("response_metadata")),
                    "metadata": Jsonb(metadata),
                },
            )
