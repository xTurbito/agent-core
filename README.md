# agent-core

Base reutilizable para agentes de IA de atencion a leads: responden FAQ,
**perfilan al prospecto** (senales → score → hot/warm/cold), lo calientan y lo
entregan a un asesor humano con un resumen automatico cuando esta listo.

Un **core** estable y generico; cada cliente es un **fork** que solo cambia
`app/` y su `.env`.

> Documentacion completa: [docs/arquitectura.md](docs/arquitectura.md) (que hace
> y por que existe cada modulo) · [docs/plan_de_trabajo.md](docs/plan_de_trabajo.md)
> (roadmap) · [CLAUDE.md](CLAUDE.md) (contexto para agentes de IA que trabajen
> en este repo).

## Arquitectura

```
core/   estable, generico (NUNCA se edita en un fork)
  llm.py        factory de LLM (google / anthropic / openai)
  agent.py      arma el agente + BASE_SAFETY_PROMPT + middleware de contexto
  memory.py     historial de conversacion (checkpointer memory/postgres)
  runner.py     interfaz simple: responder(session_id, mensaje)
  api.py        /health y POST /chat (con auth por API key)
  guards.py     guardianes (ej. no afirmar algo que solo una tool sabe)
  bounded_cache.py   cache acotada (dedup de mensajes)
  error_reporting.py reporte de errores (Sentry opcional)
  tracing.py    trazas por turno hacia observabilidad LLM (opcional)
  webhooks.py   verificacion HMAC generica (Meta/Shopify futuros)
  settings.py   config desde .env (pydantic-settings)

app/    especifico del cliente (esto es lo que se reescribe por fork)
  bootstrap.py       arma el runner: settings + tools + prompt + contexto
  prompts/           prompt del negocio (reglas comerciales del cliente)
  tools/             tools del negocio (disponibilidad, catalogo, ...)
  memory/            perfiles de contacto/conversacion + contexto para el LLM
  business/          senales, calificacion, politicas de handoff, resumidor
  channels/          canales de entrada (hoy: webhook de Kommo)
  integrations/      clientes HTTP de terceros (hoy: API de Kommo)

main.py       une todo: create_app(build_runner())
scripts/      migraciones de BD (tablas propias + checkpointer)
```

Regla de oro: **`core` nunca importa de `app`**. La dependencia va
`main → app → core`. Lo que core necesita del negocio le llega por parametro.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # versiones fijadas, no cambiar sueltas
cp .env.example .env                        # llenar API key del LLM y CHAT_API_KEY
```

Minimo en el `.env` para que funcione `/chat`: `LLM_PROVIDER`, `LLM_MODEL`, la
API key de ese proveedor y `CHAT_API_KEY` (cualquier string; sin ella `/chat`
rechaza todo). El body de `/chat` usa `mensaje` (no `message`) y `session_id`.

Con Postgres (produccion — en dev puedes trabajar con MEMORY_KIND=memory):

```bash
.venv/bin/python scripts/setup_postgres_memory.py   # tablas del checkpointer
.venv/bin/python scripts/setup_app_db.py            # tablas de perfiles/uso
```

## Correr

```bash
.venv/bin/uvicorn main:app --port 8000   # UN solo worker (estado en memoria)
```

Probar:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CHAT_API_KEY" \
  -d '{"session_id":"cliente-1","mensaje":"Hola"}'
```

`/chat` y el webhook de Kommo son **fail-closed**: sin `CHAT_API_KEY` /
`KOMMO_WEBHOOK_SECRET` en el `.env` rechazan todo. Es a proposito.

## Quickstart: levantarlo y conversar en local

Para alguien que acaba de clonar el repo y quiere ver al agente funcionando
(sin Postgres ni Kommo).

**Requisito:** Python 3.12 o superior (probado en 3.12 y 3.14).

> **Windows:** los comandos del README usan rutas de Linux/macOS
> (`.venv/bin/python`). En Windows cambia `.venv/bin/python` por
> `.venv\Scripts\python.exe`, `.venv/bin/pip` por `.venv\Scripts\pip.exe` y
> `.venv/bin/uvicorn` por `.venv\Scripts\uvicorn.exe`. Alternativa: activa el
> venv (`.venv\Scripts\activate`) y usa `python`, `pip` y `uvicorn` a secas.

```bash
# 1. Entorno
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Config: copia el ejemplo y edita .env
cp .env.example .env
#    LLM_PROVIDER=google | anthropic | openai
#    LLM_MODEL=<modelo de ese proveedor>
#    GOOGLE_API_KEY= / ANTHROPIC_API_KEY= / OPENAI_API_KEY=  (la del proveedor)
#    MEMORY_KIND=memory
#    CHAT_API_KEY=cualquier-string   (solo si vas a usar el servidor HTTP)
```

**Opcion A — chat en terminal (la mas simple, no necesita servidor):**

```bash
.venv/bin/python -m scripts.chat_cli
```

Escribes, el agente contesta con el prompt y las tools del fork. `/nuevo`
reinicia la conversacion, `/salir` termina. Con `MEMORY_KIND=memory` el
historial vive solo mientras corre el proceso.

**Opcion B — servidor HTTP** (lo que usan Kommo y cualquier front):

```bash
.venv/bin/uvicorn main:app --port 8000      # UN solo worker
```

- Navegador: `http://127.0.0.1:8000/docs` (Swagger). Pulsa Authorize, pega tu
  `CHAT_API_KEY`, y prueba `POST /chat` con `{"session_id": "x", "mensaje": "Hola"}`.
  Reusa el mismo `session_id` para continuar la conversacion.
- Terminal: el `curl` de la seccion "Correr".

**Como saber que todo esta bien:**

1. `.venv/bin/python -m tests.test_settings` y los demas tests pasan (no usan red).
2. `curl http://127.0.0.1:8000/health` responde `{"status":"ok",...}`.
3. Un mensaje en el chat regresa texto del LLM. Si ves `401` o "invalid api
   key", la key del `.env` no corresponde al `LLM_PROVIDER`. Si `/chat` da 422,
   el campo es `mensaje`, no `message`.

## Tests

Viven en `tests/` y se corren como modulo desde la raiz del repo:

```bash
.venv/bin/python -m tests.test_qualification        # scoring y politicas de handoff
.venv/bin/python -m tests.test_signal_detection     # regex de senales
.venv/bin/python -m tests.test_safety_prompt        # safety prompt siempre presente
.venv/bin/python -m tests.test_context_middleware   # inyeccion de contexto
.venv/bin/python -m tests.test_settings             # fail-fast sin API key
.venv/bin/python -m tests.test_llm_timeout          # timeout por default
.venv/bin/python -m tests.test_empty_response_retry # vacio de Gemini no se persiste
.venv/bin/python -m tests.test_tool_claim_guard     # no afirmar sin tool que respalde
.venv/bin/python -m tests.test_kommo_client         # limites y adaptacion de Kommo
.venv/bin/python -m tests.test_abuse_detection      # insultos/jailbreak/ruido
.venv/bin/python -m tests.test_agrupado_mensajes    # mensajes seguidos en un turno
.venv/bin/python -m tests.test_date_normalization   # fechas relativas
.venv/bin/python -m tests.test_agent_runner         # runner: locks y agrupado por sesion
.venv/bin/python -m tests.test_api_health           # healthcheck profundo
.venv/bin/python -m tests.test_bounded_cache        # cache acotada
.venv/bin/python -m tests.test_error_reporting      # reporte de errores
```

Corren sin red y sin BD. Correlos antes de commitear cambios a `core/` o
`app/business/`. Los scripts de `scripts/smoke/` son de humo manual: llaman al
LLM y BD reales y cuestan tokens.

## Crear un fork por cliente

1. Clona este repo con el nombre del cliente y apunta `origin` a SU repo:
   ```bash
   git clone https://github.com/xTurbito/agent-core.git chatbot-cliente
   cd chatbot-cliente
   git remote set-url origin <repo-del-cliente>
   git remote add core-upstream https://github.com/xTurbito/agent-core.git
   ```
2. Personaliza `app/`:
   - `prompts/system.py` — identidad + reglas comerciales (no inventar precios,
     no prometer entregas, no descuentos...). Las reglas de seguridad ya vienen
     de core, no las repitas.
   - `tools/` — conecta las APIs reales del cliente.
   - `business/custom_signal_patterns.py` — senales propias del giro.
   - `HANDOFF_POLICY` en `.env` — `default`, `appointment_agent` o `sales_agent`.
3. Configura su `.env` completo: API key del LLM, `POSTGRES_URL` propio,
   `MEMORY_KIND=postgres`, `CHAT_API_KEY`, y si usa Kommo: token, secreto de
   webhook (la URL registrada en Kommo lleva `?secret=...`) y
   `KOMMO_ALLOWED_LEAD_IDS` con 2-3 leads para el piloto.
4. Corre los dos scripts de BD y los tests.

### Piloto seguro (canary)

`KOMMO_ALLOWED_LEAD_IDS` limita el bot a una whitelist de leads: arranca con
2-3 de prueba, amplia gradualmente, y quita la variable cuando confies. El
campo "IA pausada" en Kommo es el boton de apagado por lead individual.

### Traer mejoras del core a un fork

```bash
git fetch core-upstream
git checkout core-upstream/main -- core/
.venv/bin/python -m tests.test_safety_prompt && .venv/bin/python -m tests.test_context_middleware
git commit -m "Sync core/ desde agent-core"
```

Sobreescritura limpia, nunca merge — funciona porque `core/` jamas se edita
dentro del fork.
