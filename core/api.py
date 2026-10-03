"""Webhook HTTP generico del bot.

Recibe {session_id, mensaje}, devuelve la respuesta del agente.
Generico: RECIBE el runner ya armado. No sabe de tools ni negocio.
"""

import secrets
from collections.abc import Callable
from logging import getLogger
from time import perf_counter
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.runner import AgentRunner
from core.settings import settings

logger = getLogger(__name__)

def require_chat_api_key(authorization: str | None = Header(default=None)) -> None:
    """Exige 'Authorization: Bearer <CHAT_API_KEY>' en /chat.

    Fail-closed a proposito: si CHAT_API_KEY no esta configurada, se
    rechaza todo en vez de dejar el endpoint abierto por descuido.
    """
    if not settings.chat_api_key:
        raise HTTPException(status_code=503, detail="CHAT_API_KEY no configurada")

    expected = f"Bearer {settings.chat_api_key}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="No autorizado")


class ChatRequest(BaseModel):
    session_id: str
    mensaje: str = Field(max_length=settings.max_message_length)


class ChatResponse(BaseModel):
    respuesta: str


ErrorHandler = Callable[[Exception, dict[str, Any]], None]
UsageLogger = Callable[[dict[str, Any]], None]


def create_app(
    runner: AgentRunner,
    on_error: ErrorHandler | None = None,
    log_usage: UsageLogger | None = None,
) -> FastAPI:
    app = FastAPI(title="Chatbot Core")

    @app.get("/health")
    def health():
        checks: dict[str, str] = {}
        healthy = True

        if settings.postgres_url:
            try:
                with psycopg.connect(settings.postgres_url, connect_timeout=3) as conn:
                    conn.execute("SELECT 1")
                checks["postgres"] = "ok"
            except Exception:
                # No se expone el detalle del error en la respuesta (podria
                # filtrar credenciales de la URL de conexion); queda en el log.
                logger.exception("Healthcheck: Postgres no responde")
                checks["postgres"] = "unreachable"
                healthy = False
        else:
            checks["postgres"] = "not configured"

        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "degraded", "checks": checks},
        )

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_chat_api_key)])
    def chat(req: ChatRequest) -> ChatResponse:
        started_at = perf_counter()

        try:
            result = runner.responder_con_metadata(req.session_id, req.mensaje)
            respuesta = result["text"]
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)

            if on_error:
                on_error(
                    exc,
                    {
                        "source": "chat",
                        "session_id": req.session_id,
                    },
                )

            if log_usage:
                log_usage(
                    {
                        "source": "chat",
                        "session_id": req.session_id,
                        "status": "error",
                        "reason": "agent failed",
                        "message_length": len(req.mensaje),
                        "latency_ms": latency_ms,
                    }
                )

            respuesta = (
                "Ahora no puedo revisar esa información. Un asesor te apoyará en breve."
            )
        else:
            latency_ms = round((perf_counter() - started_at) * 1000)

            if log_usage:
                log_usage(
                    {
                        "source": "chat",
                        "session_id": req.session_id,
                        "status": "ok",
                        "message_length": len(req.mensaje),
                        "response_length": len(respuesta),
                        "latency_ms": latency_ms,
                        "usage_metadata": result["usage_metadata"],
                        "response_metadata": result["response_metadata"],
                    }
                )

        return ChatResponse(respuesta=respuesta)

    return app
