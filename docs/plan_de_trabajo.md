# Plan de trabajo — ChatBotTBS (core base de agentes)

Contexto: `ChatBotTBS` es la base generica para 3 clientes reales:
- **Salon de belleza** — canal Kommo, agenda real en `AgendaSystem` (.NET)
- **Clinica psicologica** — canal WhatsApp directo, agenda real en `AgendaSystem` (.NET)
- **Tienda de bicis electricas** — fork `ChatBicimoto`, catalogo Shopify

Regla de oro que se mantiene: `core/` generico y reutilizable, `app/` especifico por fork, `core` nunca importa de `app`.

---

## Fase 0 — Arreglar ahora (riesgo real, bajo esfuerzo)

- [ ] **Arreglar el remoto git de este repo.** `origin` apunta hoy a `github.com/xTurbito/ChatBicimoto.git` (el repo del cliente de bicis). Un `git push` sin fijarse mezclaria el codigo de este repo (base generica) con el repo especifico de bicis. Crear/asignar un remoto propio para `ChatBotTBS` antes de cualquier push.
- [ ] **Autenticacion en `/chat`.** Hoy [core/api.py](../core/api.py) no valida nada — cualquiera que llegue a la URL puede chatear gratis con el LLM o ensuciar perfiles. Agregar validacion de un token compartido (header `Authorization` o similar) via `core/settings.py`.
- [ ] **Validar origen del webhook de Kommo.** [app/channels/kommo.py](../app/channels/kommo.py) procesa el payload sin verificar firma/secreto — alguien puede inyectar eventos falsos. Revisar que firma/secreto ofrece Kommo para webhooks y validarla antes de procesar.
- [ ] **Limite de tamano de mensaje entrante** (`/chat` y Kommo) — evita abuso de costo y payloads de injection gigantes.

## Fase 1 — Robustez del core (antes de escalar a mas clientes)

- [ ] **Pool de conexiones Postgres** en `app/memory/profiles.py` — hoy abre una conexion nueva por query.
- [ ] **Logging real** — reemplazar los `print()` de `kommo.py` / `kommo_client.py` / `usage.py` por `logging` con niveles.
- [ ] **Fail-fast en `core/settings.py`** — si `LLM_PROVIDER=anthropic` sin `ANTHROPIC_API_KEY`, debe fallar al arrancar, no a medio request.
- [ ] **`AgentRunner._locks` sin limite** ([core/runner.py](../core/runner.py)) — crece para siempre, un `Lock()` por cada `session_id` historico. Revisar estrategia de limpieza (TTL, LRU, o aceptar el costo si es chico).
- [ ] **Tests de negocio** — `qualification.py` y `signal_detection.py` son logica pura, faciles de testear (pesos de senales, umbrales de escalamiento).
- [ ] **Formalizar el test de seguridad** — el intento de prompt injection que probamos manualmente deberia quedar como test permanente (`test_safety_prompt.py`) para detectar regresiones futuras al prompt.

## Fase 2 — Conectar los 3 clientes reales

- [ ] **Decidir y documentar el mecanismo de sync de `core/`** entre forks: `git remote add core-upstream <url>` + `git checkout core-upstream/main -- core/` (sobreescritura limpia, ya que `core/` nunca se toca localmente). Documentar el procedimiento en el README.
- [ ] **Poner al dia `ChatBicimoto`** — sigue en el estado pre-refactor (system prompt todavia dice "clinica dental", `app/kommo.py` plano, sin middleware de contexto ni safety prompt). Traer `core/` actualizado y adaptar `app/` al patron nuevo (`channels/business/integrations`).
- [ ] **Integracion Shopify** para el fork de bicis — nueva tool/`app/integrations/shopify_client.py` para catalogo real (hoy no existe).
- [ ] **Canal WhatsApp directo** (clinica psicologica) — nuevo `app/channels/whatsapp.py` (decidir proveedor: WhatsApp Business API oficial, Twilio, u otro).
- [ ] **Conectar `consultar_disponibilidad` a `AgendaSystem` real** (salon + clinica) — hoy es un mock hardcodeado ([app/tools/disponibilidad.py](../app/tools/disponibilidad.py)); reemplazar por llamada real a la API .NET de `AgendaSystem`.
- [ ] **Cerrar el loop de handoff por canal** — decidir la accion concreta por canal (ej. en Kommo: pausar IA + escribir el resumen en un campo, cuando ese campo exista; en WhatsApp: decidir a quien y como se notifica).

## Fase 3 — Preparar para escala real

- [ ] **`MEMORY_KIND=postgres` como default** para cualquier cliente en produccion (in-memory no sobrevive un restart ni multiples workers).
- [ ] **Revisar tamano del threadpool / llamadas async al LLM** si el volumen de mensajes concurrentes crece.
- [ ] **Manejo de secretos mas alla de `.env`** una vez haya 2-3 clientes en produccion simultaneo.
- [ ] **Politica de datos sensibles para la clinica psicologica** — cifrado en reposo de `contact_profiles`/`conversation_profiles` y retencion/borrado, dado que ahi se toca informacion de salud mental.

---

## Como usar este documento

Es un checklist vivo — marca `[x]` conforme cierres cada punto y agrega lo que surja. La prioridad sugerida es el orden de las fases, pero Fase 0 y partes de Fase 1 (seguridad) deberian ir primero sin importar en que cliente estes trabajando, porque aplican a cualquier fork que uses.
