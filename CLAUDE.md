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

## Comandos

```bash
.venv/bin/python test_qualification.py        # los 4 corren sin red ni BD
.venv/bin/python test_signal_detection.py
.venv/bin/python test_safety_prompt.py
.venv/bin/python test_context_middleware.py

.venv/bin/uvicorn main:app --port 8000        # servidor (UN worker, ver abajo)
.venv/bin/python scripts/setup_app_db.py      # migraciones de tablas propias
```

Convenciones: tests = scripts planos con assert (sin pytest). Codigo y
comentarios en espanol sin acentos. Referencias de dinero/negocio en espanol.

## Trampas conocidas (nos han mordido)

- **El `.env` local apunta a una BD de negocio REAL compartida** (tiene tablas
  de produccion tipo `Personas`, `Citas`, `Pagos` de AgendaSystem). No siembres
  datos de prueba sin marcarlos (`source='test_...'`) y no borres nada que no
  hayas creado.
- **Un solo worker de uvicorn**: locks por sesion, cache de dedup y
  `pending_ai_responses` viven en memoria del proceso. Dos workers = respuestas
  dobles y estado partido.
- **`MEMORY_KIND=memory` pierde TODAS las conversaciones al reiniciar** el
  proceso. Solo para desarrollo.
- **Gemini con thinking regresa bloques, no string** — cualquier salida de LLM
  hacia el usuario debe pasar por `extract_text()` de `core/runner.py`.
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
