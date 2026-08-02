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
cp .env.example .env                        # llenar API key del LLM como minimo
```

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
