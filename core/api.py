"""Webhook HTTP generico del bot.

Recibe {session_id, mensaje}, devuelve la respuesta del agente.
Generico: RECIBE el runner ya armado. No sabe de tools ni negocio.
"""

import secrets
from collections.abc import Callable
from time import perf_counter
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from core.runner import AgentRunner
from core.settings import settings


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
        return {"status": "ok"}

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
