# Plan de trabajo — agent-core

Contexto: este repo es la base generica (`agent-core`) para 3 clientes reales:
- **Salon de belleza** — canal Kommo, agenda real en `AgendaSystem` (.NET)
- **Clinica psicologica** — canal WhatsApp directo, agenda real en `AgendaSystem` (.NET)
- **Tienda de bicis electricas** — fork `ChatBicimoto`, catalogo Shopify (consulta saliente, sin webhook de Shopify)

Regla de oro que se mantiene: `core/` generico y reutilizable, `app/` especifico por fork, `core` nunca importa de `app`.

**Estado: base congelada en v0.1.0.** Features nuevas van en los forks de cliente; este repo solo recibe fixes y mejoras genericas probadas. La estrategia de salida: piloto controlado con UN cliente usando la whitelist `KOMMO_ALLOWED_LEAD_IDS` como canary.

---

## Fase 0 — Seguridad basica ✅ CERRADA (v0.1.0)

- [x] **Remoto git corregido** — `origin` ahora apunta a `github.com/xTurbito/agent-core.git` (apuntaba al repo de ChatBicimoto por error).
- [x] **Autenticacion en `/chat`** — Bearer `CHAT_API_KEY`, fail-closed, en [core/api.py](../core/api.py).
- [x] **Secreto del webhook de Kommo** — `?secret=<KOMMO_WEBHOOK_SECRET>` obligatorio, fail-closed (Kommo no soporta firma HMAC ni headers custom). Ademas: dedup por `message_id` con cache acotado (Kommo reintenta webhooks).
- [x] **Limite de tamano de mensaje** — `/chat` via Pydantic (422 automatico), Kommo via check por request. `MAX_MESSAGE_LENGTH`, default 4000.
- [x] *(extra)* **`python-multipart` faltaba instalado** — sin el, NINGUN webhook form-encoded de Kommo funcionaba.

## Fase 1 — Robustez del core

- [x] **Tests de negocio** — `test_qualification.py` (pesos, umbrales, politicas) y `test_signal_detection.py` (regex + custom patterns).
- [x] **Test de seguridad** — `test_safety_prompt.py`: `build_agent` siempre antepone `BASE_SAFETY_PROMPT` con sus reglas clave.
- [x] **Versiones fijadas en requirements.txt** — LangChain/LangGraph rompen APIs seguido; los pins se actualizan juntos y con los tests en verde.
- [ ] **Pool de conexiones Postgres** en `app/memory/profiles.py` — hoy abre una conexion nueva por query. *(post-piloto)*
- [ ] **Logging real** — reemplazar los `print()` de `kommo.py` / `kommo_client.py` / `usage.py` por `logging` con niveles. *(post-piloto)*
- [ ] **Fail-fast en `core/settings.py`** — si `LLM_PROVIDER=anthropic` sin `ANTHROPIC_API_KEY`, fallar al arrancar, no a medio request. *(rapido, puede entrar antes del piloto)*
- [ ] **`AgentRunner._locks` sin limite** ([core/runner.py](../core/runner.py)) — un `Lock()` por session_id historico, nunca se libera. *(post-piloto; mismo patron de cache acotado que el dedup de kommo.py)*

## Fase 2 — Primer piloto en produccion (fork del cliente, NO este repo)

El spec del primer cliente (ventas: calificar 7 datos, FAQ, calentar, entregar a asesora) se implementa en SU fork. Orden del camino critico:

- [ ] **Crear el fork del cliente** desde agent-core (clonar, cambiar origin, agregar core-upstream — procedimiento en el README).
- [ ] **Prompt de calificacion activa** — el system prompt del fork instruye recabar naturalmente: tipo de cliente, producto de interes, cantidad, ciudad/estado, fecha estimada de compra, urgencia, catalogo/cotizacion/info. Mas las reglas comerciales: no inventar precios, no prometer entregas sin validar, no descuentos, no cerrar ventas.
- [ ] **Extraccion de datos a `important_data`** — paso LLM post-turno (mismo patron que el resumidor) que guarda los datos capturados; el contexto reinyectado le recuerda al agente que le falta preguntar.
- [ ] **FAQ precargada** — `app/knowledge/faq.md` del cliente inyectada al prompt (RAG solo si el catalogo crece).
- [ ] **Escritura a Kommo** — `update_lead_fields` / `add_lead_tags` / `move_lead_stage` / `add_lead_note` en `kommo_client.py`, conectadas al momento del handoff: pausar IA + resumen visible para la asesora + mover etapa. Cierra el loop de handoff end-to-end.
- [ ] **Deploy piloto**: HTTPS publico, systemd/Docker, UN worker de uvicorn, `MEMORY_KIND=postgres`, secrets reales en `.env`, whitelist con 2-3 leads → ampliar gradual → quitar whitelist.
- [ ] **Prueba end-to-end contra Kommo real** — WhatsApp real → webhook → respuesta en el chat via salesbot. (Todo lo probado hasta ahora fue simulado.)

## Fase 3 — Siguientes clientes y escala

- [ ] **Seguimientos automaticos a leads frios** — scheduler que detecta conversaciones estancadas en `conversation_profiles` y dispara follow-up via salesbot, con reglas anti-spam (max 2-3 intentos espaciados). *(el cliente lo pidio; entra despues de que el piloto ande)*
- [ ] **Poner al dia `ChatBicimoto`** — sigue pre-refactor (prompt de "clinica dental", `app/kommo.py` plano, sin middleware ni safety prompt). Sync de `core/` + migrar `app/` al patron `channels/business/integrations`.
- [ ] **Integracion Shopify (bicis)** — tool de consulta de catalogo. Candidato natural al patron subagente: las busquedas multi-query viven en contexto aislado y solo la conclusion vuelve al hilo principal.
- [ ] **Canal WhatsApp directo (clinica)** — `app/channels/whatsapp.py`; el webhook de Meta SI firma (HMAC `X-Hub-Signature-256`) — usar `core/webhooks.py` que ya esta listo.
- [ ] **`SummarizationMiddleware` para historial largo** — la version instalada de langchain ya lo trae; entra cuando haya conversaciones reales largas que lo justifiquen (vigilar `usage_metadata` en `usage_logs` como metrica).
- [ ] **Cola/worker para rafagas** — ACK inmediato al webhook + procesamiento aparte. Empezar con cola en proceso (asyncio), broker real solo con datos que lo justifiquen.
- [ ] **Politica de datos sensibles para la clinica psicologica** — cifrado en reposo de perfiles y retencion/borrado (informacion de salud mental).
- [ ] **Secretos mas alla de `.env`** con 2-3 clientes en produccion simultanea.

---

## Como usar este documento

Checklist vivo — marca `[x]` conforme cierres y agrega lo que surja. El orden manda: nada de Fase 3 antes de que el piloto de Fase 2 este corriendo con leads reales. La deuda tecnica marcada *(post-piloto)* esta congelada a proposito: es problema de escala y hoy el trafico es cero.
