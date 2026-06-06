# agent-core

Base reutilizable para construir agentes de IA (bots de WhatsApp y otros) por negocio.
Un **core** estable y genérico; cada cliente es un **fork** que solo cambia `app/` y su `.env`.

## Arquitectura

```
core/   estable, genérico (no se toca en el fork)
  llm.py        factory de LLM (google / anthropic / openai)
  agent.py      arma el agente (LangGraph create_agent)
  memory.py     memoria de conversación (checkpointer)
  runner.py     interfaz simple: responder(session_id, mensaje)
  settings.py   config desde .env (pydantic-settings)
  api.py        webhook FastAPI: /health y POST /chat
app/    específico del cliente
  bootstrap.py  arma el runner: settings + tools + prompt
  tools/        tools del negocio
  prompts/      prompts del bot
main.py         une todo: create_app(build_runner())
```

Regla de oro: **`core` nunca importa de `app`**. La dependencia va `main → app → core`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # y llena tu GOOGLE_API_KEY
```

## Correr la API

```bash
.venv/bin/uvicorn main:app --port 8000
```

Probar:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"cliente-1","mensaje":"Hola"}'
```

## Crear un fork por cliente

1. Forkea / clona este repo.
2. Edita `app/tools/` con las tools del negocio.
3. Edita `SYSTEM_PROMPT` y `TOOLS` en `app/bootstrap.py`.
4. Configura el `.env` del cliente.

El `core/` queda intacto; las mejoras del core se traen con `git pull`.
