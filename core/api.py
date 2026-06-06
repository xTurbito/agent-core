"""Webhook HTTP generico del bot.

Recibe {session_id, mensaje}, devuelve la respuesta del agente.
Generico: RECIBE el runner ya armado. No sabe de tools ni negocio.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from core.runner import AgentRunner


class ChatRequest(BaseModel):
    session_id: str
    mensaje: str


class ChatResponse(BaseModel):
    respuesta: str


def create_app(runner: AgentRunner) -> FastAPI:
    app = FastAPI(title="Chatbot Core")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        respuesta = runner.responder(req.session_id, req.mensaje)
        return ChatResponse(respuesta=respuesta)

    return app
