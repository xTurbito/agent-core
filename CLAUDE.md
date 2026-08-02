# CLAUDE.md — contexto para agentes de IA trabajando en este repo

## Que es esto

`agent-core`: base reutilizable (fork por cliente) para agentes de IA que
atienden leads por WhatsApp/CRM — FAQ + perfilamiento + handoff a asesor
humano. Este repo es LA BASE; los clientes reales (salon de belleza via Kommo,
clinica psicologica via WhatsApp, tienda de bicis via Kommo+Shopify) viven en
forks separados. Lee `docs/arquitectura.md` antes de tocar cualquier modulo:
explica que hace y POR QUE existe cada parte.

## Reglas que no se negocian

1. **`core/` nunca importa de `app/`.** Dependencia: `main → app → core`. Si
   core necesita algo del negocio, se inyecta por parametro (ver
   `context_provider` en `core/agent.py` como patron de referencia).
2. **Generico va en `core/`, negocio va en `app/`.** Antes de agregar algo a
   core pregunta: "¿los 3 clientes lo necesitan tal cual?" Si no, es de `app/`.
3. **No metas contexto al historial.** Todo lo dinamico que deba ver el LLM por
   turno entra via `ContextInjectionMiddleware` (modifica el ModelRequest, el
   checkpointer no lo persiste). Meter mensajes extra en `invoke()` los guarda
   PARA SIEMPRE y se duplican cada turno.
4. **Nunca quites `BASE_SAFETY_PROMPT`** ni lo muevas detras del prompt del
   fork. `test_safety_prompt.py` lo vigila.
5. **requirements.txt esta fijado a proposito.** LangChain/LangGraph rompen
   APIs seguido. No actualices pins sueltos; si actualizas, corre los 4 tests.
6. **Verifica APIs de LangChain/LangGraph con inspect antes de usarlas**, no
   asumas de memoria — ya nos ha cambiado la firma entre versiones.
7. **El prompt pide, el guardian obliga.** Cuando el agente afirme como hecho
   consumado algo que solo una tool sabe ("tu cita quedo agendada"), no lo
   arregles metiendo mas texto al prompt: es probabilistico y ya lo rompio en
   produccion. Usa `ToolClaimGuardMiddleware` de `core/guards.py`.
8. **Kommo tiene rarezas de canal**: `execute_handlers` acepta maximo 10
   bloques de 80 caracteres cada uno (~800 chars por respuesta), y algunos
   emojis modernos llegan a WhatsApp como `?`. La salida pasa por
   `app/integrations/kommo_client.py`. No lo quites sin probar en WhatsApp real.

## Comandos

```bash
# tests viven en tests/ y se corren como modulo (asi resuelven app/ y core/):
.venv/bin/python -m tests.test_qualification   # puras, sin red ni BD
.venv/bin/python -m tests.test_signal_detection
.venv/bin/python -m tests.test_safety_prompt
.venv/bin/python -m tests.test_context_middleware
.venv/bin/python -m tests.test_settings
.venv/bin/python -m tests.test_llm_timeout
.venv/bin/python -m tests.test_empty_response_retry
.venv/bin/python -m tests.test_tool_claim_guard
.venv/bin/python -m tests.test_kommo_client
.venv/bin/python -m tests.test_abuse_detection
.venv/bin/python -m tests.test_agrupado_mensajes
.venv/bin/python -m tests.test_date_normalization

.venv/bin/uvicorn main:app --port 8000        # servidor (UN worker, ver abajo)
.venv/bin/python scripts/setup_app_db.py      # migraciones de tablas propias
```

Convenciones: tests = scripts planos con assert (sin pytest). Codigo y
comentarios en espanol sin acentos. Referencias de dinero/negocio en espanol.
Los scripts que pegan a LLM/BD reales (requieren env exportado) viven en
`scripts/smoke/`, fuera de la bateria offline de `tests/`.

## Trampas conocidas (nos han mordido)

- **El `.env` local puede apuntar a una BD de negocio REAL compartida.** Antes
  de sembrar datos de prueba, marcalos (`source='test_...'`) y no borres nada
  que no hayas creado.
- **Sin timeout, una llamada colgada al LLM cuelga la sesion para siempre.**
  `core/llm.py` fija 30s por default; visto en pruebas de carga con 8 sesiones.
- **Un solo worker de uvicorn**: locks por sesion, cache de dedup y
  `pending_ai_responses` viven en memoria del proceso. Dos workers = respuestas
  dobles y estado partido.
- **`MEMORY_KIND=memory` pierde TODAS las conversaciones al reiniciar** el
  proceso. Solo para desarrollo.
- **Gemini con thinking regresa bloques, no string** — cualquier salida de LLM
  hacia el usuario debe pasar por `extract_text()` de `core/runner.py`.
- **Gemini a veces regresa un AIMessage vacio** (finish STOP, 0 tokens). Si ese
  vacio se persiste en el checkpoint la sesion queda muda para siempre: los
  turnos siguientes imitan el patron del historial. Por eso
  `EmptyResponseRetryMiddleware` reintenta ANTES de persistir.
- **Los endpoints de Kommo devuelven JSON a Kommo, no al lead.** Lo unico que
  el lead ve es `respuesta` via `continue_salesbot`. No "mejores" esos JSON
  pensando que son mensajes de usuario.
- **El orden en el webhook importa**: senales/handoff se aplican DESPUES de
  responder y en threadpool (el resumen llama al LLM; sincrono en el endpoint
  async congela el servidor, y antes de responder el resumen sale incompleto).
- **Shell/git**: hay repos hermanos en `~/Documents` (ChatBot, ChatBicimoto).
  Usa `git -C <ruta absoluta>`; un `cd` persistente ya causo un remote cambiado
  en el repo equivocado.

## Seguridad ya implementada (no la degrades)

`/chat`: Bearer `CHAT_API_KEY`, fail-closed, limite de tamano (Pydantic).
Webhook Kommo: `?secret=` obligatorio (fail-closed), dedup por `message_id`
(cache acotado 2000), limite de tamano. `core/webhooks.py` tiene HMAC generico
listo para canales que si firman (Meta/Shopify).

## Estado y roadmap

Base congelada en v0.1.0 — el trabajo de features nuevas va en los forks de
cliente, no aqui. Pendientes y su prioridad: `docs/plan_de_trabajo.md`.
Deuda tecnica deliberada (pool de BD, logging, cola, summarization de
historial): documentada al final de `docs/arquitectura.md`, congelada hasta que
el primer piloto este en produccion.
