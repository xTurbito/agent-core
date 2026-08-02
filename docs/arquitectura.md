# Arquitectura de agent-core

Que hace cada parte del proyecto y **por que existe**. Si vas a tocar un modulo,
lee su seccion primero: casi todas las decisiones raras tienen una razon que ya
nos mordio una vez.

## El proposito del proyecto

Base reutilizable para agentes de IA de atencion a leads (FAQ + perfilamiento +
handoff a humano). Un solo repo estable (`agent-core`); cada cliente es un
**fork** que solo cambia `app/` y su `.env`. Clientes reales que salen de aqui:
salon de belleza (Kommo), clinica psicologica (WhatsApp), tienda de bicis
electricas (Kommo + catalogo Shopify).

El ciclo que hace valiosa esta base (y que un bot simple no puede hacer):

```
lead habla → senales detectadas → score/etiqueta calculados → guardado en Postgres
    ↑                                                                  ↓
agente pregunta lo que falta ← contexto reinyectado al prompt ← perfil leido
```

## La regla de oro

**`core/` nunca importa de `app/`.** La dependencia va `main → app → core`.
Todo lo que `core` necesita del negocio le llega por parametro (funciones
inyectadas, como `context_provider`). Asi las mejoras de core se propagan a
cualquier fork sin arrastrar negocio ajeno.

Mecanismo de sync hacia un fork:

```bash
git remote add core-upstream https://github.com/xTurbito/agent-core.git  # una vez
git fetch core-upstream
git checkout core-upstream/main -- core/
git commit -m "Sync core/ desde agent-core"
```

Funciona porque `core/` jamas se edita dentro de un fork: es sobreescritura
limpia, nunca merge.

---

## core/ — generico, estable, se sincroniza entre forks

### core/llm.py
Factory de chat models (google / anthropic / openai) con la misma interfaz
LangChain. **Por que existe:** cambiar de proveedor de LLM debe ser un cambio
de `.env`, no de codigo. Los imports van adentro de cada rama para no cargar
SDKs que el fork no usa. Fija `timeout=30s` por default: **sin timeout una
llamada colgada al proveedor cuelga el lock por-sesion de `AgentRunner` para
siempre** (visto en pruebas de carga con 8 sesiones concurrentes).

### core/agent.py
Arma el agente (LangGraph `create_agent`) y contiene tres piezas de seguridad:

- **`BASE_SAFETY_PROMPT`**: reglas anti prompt-injection, no revelar datos
  internos del CRM (scores, etiquetas hot/warm/cold, motivos de escalamiento) y
  no salirse del giro del negocio. Se antepone SIEMPRE al prompt del fork.
  **Por que en core:** todo fork lo hereda gratis; nadie tiene que acordarse de
  escribirlo. Verificado en vivo contra intentos reales de injection.
  `test_safety_prompt.py` truena si un refactor lo desconecta.
- **`ContextInjectionMiddleware`**: en cada turno llama al `context_provider`
  inyectado (una funcion `session_id -> str | None`) y pega el resultado al
  system message via `wrap_model_call`. **Por que middleware y no un mensaje en
  `invoke()`:** si el contexto entrara como mensaje, el checkpointer lo
  persistiria y se acumularia duplicado en cada turno. El middleware modifica
  el `ModelRequest` justo antes del LLM y el historial guardado nunca lo ve;
  cada turno se recalcula fresco desde Postgres. El `session_id` sale de
  `get_config()["configurable"]["thread_id"]` (LangGraph lo propaga por
  contextvar durante el invoke).
- **`EmptyResponseRetryMiddleware`**: reintenta cuando el modelo regresa un
  mensaje sin texto ni tool_calls. **Por que:** Gemini a veces contesta vacio
  (finish STOP, 0 tokens); si ese vacio se persiste en el checkpoint la sesion
  queda MUDA, porque los turnos siguientes imitan el patron vacio del
  historial. Por eso el reintento va antes de persistir, con un empujon en el
  system prompt para romper el determinismo del caso que fallo.

`build_agent` acepta ademas `extra_middleware`: ahi cada fork engancha sus
guardianes de dominio sin que core sepa de ellos.

### core/guards.py
**`ToolClaimGuardMiddleware`**: lee el borrador ANTES de que salga y, si afirma
como hecho consumado algo que solo una tool sabe sin que esa tool haya
respondido con exito en ESTE turno, reintenta la generacion con una correccion
inyectada. **Por que existe:** el system prompt es probabilistico. Por mas
explicita que sea la regla, el modelo afirmo citas inexistentes y horarios que
nunca consulto — dos veces en pruebas reales, con la regla escrita. Un
guardian no depende de que el LLM obedezca.

Se parametriza con `claim_detector` (¿el texto AFIRMA el hecho?), `tool_name`,
`success_marker` (la tool tuvo que responder BIEN: un error no respalda nada) y
`nudge`. El detector debe distinguir afirmacion de invitacion ("tu cita quedo
agendada" si, "¿te gustaria agendar?" no) o el guardian reintenta de mas y
encarece cada turno. La busqueda del respaldo se corta en el ultimo mensaje del
usuario a proposito: una consulta exitosa de hace tres turnos no respalda lo
que el agente afirma hoy.

### core/memory.py
Factory del checkpointer (historial de conversacion por `thread_id`).
`memory` = RAM, solo para desarrollo: **un reinicio del proceso borra todas las
conversaciones a la mitad**. En produccion siempre `postgres` (tablas
`checkpoints*`, las administra LangGraph via `scripts/setup_postgres_memory.py`).

### core/runner.py
La interfaz que el resto del sistema usa: `responder(session_id, mensaje)`.
Esconde LangGraph por completo.

- **Lock por sesion**: serializa mensajes del MISMO lead (dos webhooks del mismo
  lead no se pisan el historial); leads distintos corren en paralelo. Deuda
  conocida: el dict de locks crece sin limite (uno por session_id historico).
- **`extract_text()`**: normaliza el content del LLM a texto plano. **Por que:**
  Gemini con thinking devuelve una lista de bloques con firmas internas de
  razonamiento; sin esto, esos bloques se filtraban tal cual al cliente final
  (paso en pruebas reales).
- **`get_conversation_messages()`**: expone el historial real del checkpointer.
  Existe para que el resumidor de handoff trabaje sobre la conversacion
  completa, no sobre una reconstruccion.

### core/api.py
Webhook HTTP generico: `/health` y `POST /chat`.

- `/chat` exige `Authorization: Bearer <CHAT_API_KEY>` y es **fail-closed**: sin
  la variable configurada rechaza todo (503). **Por que:** un endpoint de LLM
  abierto es costo gratis para cualquiera que encuentre la URL.
- Limite de tamano de mensaje via Pydantic `Field(max_length=...)` — FastAPI
  regresa 422 antes de tocar al agente. Ojo: el limite se fija al importar el
  modulo (arranque del server), no se puede cambiar en caliente.
- Si el agente truena, el cliente recibe un mensaje neutro de fallback; el
  detalle va a `on_error` y `log_usage` (inyectados desde `main.py`), nunca al
  cliente.

### core/webhooks.py
`verify_hmac_signature()`: verificacion HMAC generica en tiempo constante, con
soporte de prefijo (formato Meta `sha256=<hex>`). **Por que existe ya:** Kommo
no firma webhooks (por eso usa secreto en URL), pero WhatsApp/Meta y Shopify si
firman; cuando se construyan esos canales, la primitiva ya esta y no se
reescribe por canal.

### core/settings.py
Unica fuente de config, leida del `.env` (pydantic-settings). Incluye
`active_llm_api_key` (elige la key segun el provider) y los valores de
seguridad (`chat_api_key`, `kommo_webhook_secret`, `max_message_length`).

---

## app/ — especifico del cliente, se reescribe por fork

### app/bootstrap.py
El punto de composicion del fork: junta settings + tools + prompt + contexto y
arma el `AgentRunner`. Es el UNICO lugar donde se decide que tools y que
`context_provider` usa este cliente.

### app/prompts/system.py
El prompt del negocio (hoy es un placeholder de clinica dental). Aqui van las
reglas comerciales del cliente (no inventar precios, no prometer entregas, no
dar descuentos, no cerrar ventas) — las de seguridad ya vienen de core.

### app/tools/
Tools del negocio. `disponibilidad.py` es un mock marcado con TODO; en cada
fork se reemplaza por la API real (AgendaSystem para salon/clinica, Shopify
para bicis).

### app/memory/profiles.py
La memoria de negocio: `contact_profiles` (quien es la persona, entre canales)
y `conversation_profiles` (estado de UNA conversacion: score, etiqueta,
handoff, resumen, `important_data` JSONB para los datos de calificacion).
**Por que tablas propias y no el checkpointer:** el checkpointer guarda blobs
de LangGraph (formato interno, ilegible); estas tablas son TUYAS — legibles,
consultables, y sobreviven aunque un dia cambies de framework. Deuda conocida:
una conexion psycopg nueva por query (pool pendiente, ver plan).

### app/memory/context.py
`build_business_context()`: convierte el perfil en ~10 lineas destiladas que el
middleware inyecta al prompt. Valores recortados (`MAX_VALUE_LENGTH=160`,
`MAX_ITEMS=6`) a proposito: **contexto curado, no volcado** — mas contexto
crudo = mas ruido para el LLM. El encabezado marca la info como INTERNA (el
LLM no debe citarla al cliente; defensa en profundidad junto al safety prompt).
Regresa `None` sin `POSTGRES_URL` para que un fork sin BD siga funcionando.

### app/business/
La logica comercial, Python puro (testeable sin LLM ni BD):

- **signal_detection.py** — regex sobre el texto del lead → senales
  (`asked_price`, `requested_human`...). **Por que regex y no LLM:**
  deterministico, gratis, testeable; es la primera capa, no la unica (la
  extraccion con LLM es evolucion natural, ver plan). Cada fork agrega
  patrones en `custom_signal_patterns.py` sin tocar los base.
- **qualification.py** — pesos por senal → score 0-100 → hot/warm/cold, y
  politicas de handoff por tipo de agente (`default`, `appointment_agent`,
  `sales_agent`). Las politicas descansan en dos disparadores: senales que
  SIEMPRE escalan (ej. `requested_human`, `strong_objection` en sales) y un
  umbral de score. Es el criterio de negocio del sistema: cambiarlo es
  decision comercial, no refactor (`test_qualification.py` lo congela).
- **profile_updates.py** — `apply_conversation_signals()` junta todo: senales →
  score → handoff → actualiza el perfil. Detecta la **transicion** False→True
  de `handoff_recommended` y SOLO ahi dispara el resumen (una llamada LLM por
  lead, no una por mensaje).
- **summarizer.py** — resume la conversacion real (via
  `get_conversation_messages`) en 3-4 lineas para que la asesora retome sin
  leer todo. Se guarda en `conversation_profiles.summary`.
- **kommo_rules.py** — reglas de gating del canal: whitelist de leads
  (`KOMMO_ALLOWED_LEAD_IDS`, el mecanismo de piloto/canary) y el campo "IA
  pausada" (el boton de apagado por lead).
- **abuse_detection.py** — defensa barata (sin LLM) contra insultos directos,
  jailbreak/prompt injection y puro ruido. **Por que sin LLM:** no tiene
  sentido pagar tokens por contestarle a alguien que solo quiere romper el
  flujo. No es moderacion de contenido general.
- **agrupado_mensajes.py** — junta mensajes seguidos del mismo lead en un solo
  turno. **Por que:** en WhatsApp la gente escribe entrecortado, y cada mensaje
  disparaba su propia generacion: dos respuestas casi identicas al lead y dos
  llamadas al LLM pagadas por la misma pregunta. El estado vive en memoria del
  proceso, igual que el dedup — otra razon del worker unico.
- **date_normalization.py** — resuelve "mañana", "el sabado que viene",
  "proximo martes" a una fecha ISO, en Python puro contra
  `BUSINESS_TIMEZONE`. **Por que en codigo y no en el prompt:** el LLM no sabe
  que dia es hoy y calcula mal; en el prompt seria una apuesta.

### app/channels/kommo.py
El canal Kommo completo (webhook de mensajes + widget request del Salesbot).
Decisiones no obvias:

- **Secreto en query param** (`?secret=...`): Kommo no permite headers custom
  ni firma sus webhooks; el secreto en la URL registrada es el mecanismo
  disponible. Fail-closed.
- **Dedup por `message_id`** con cache acotado (2000 ids): Kommo reintenta
  webhooks si tardas en responder; sin esto, un reintento = respuesta doble al
  lead.
- **Las senales/handoff se aplican DESPUES de responder** y en threadpool.
  Por que: (1) el resumen de handoff debe incluir el mensaje que lo disparo y
  la despedida del bot (antes se generaba sin ellos); (2) el resumen llama al
  LLM y correrlo sincrono dentro del endpoint async congelaba el servidor
  entero.
- Los JSON `{"status": "ignored"/"error"}` que regresan los endpoints son
  respuestas HTTP a Kommo (server-to-server); el lead NUNCA los ve. Lo unico
  que llega al chat es `respuesta` via `continue_salesbot(return_url, ...)`.
- Restriccion de deploy: locks, dedup y `pending_ai_responses` viven en memoria
  del proceso → **un solo worker de uvicorn** hasta que se externalicen.

### app/channels/kommo_payloads.py
Parseo del payload form-encoded de Kommo (claves tipo `message[add][0][text]`).
Separado del canal para poder testearlo sin FastAPI.

### app/integrations/kommo_client.py
Cliente HTTP de la API de Kommo: leer lead y contacto, disparar/continuar
Salesbot, escribir custom fields, mover de etapa, cerrar como Lost, y buscar/
vincular contactos. Los **ids de la cuenta** (loss reasons, etapas intermedias
del pipeline, ids de custom fields) NO viven aqui: son de cada cuenta y van en
el fork. Solo se quedan `KOMMO_LOST_STATUS_ID` y `KOMMO_WIN_STATUS_ID`, que
Kommo reserva igual en todas las pipelines.

La parte no obvia es la adaptacion de la salida, y nos costo un 400 en
produccion con el lead sin recibir NADA:

- **Dos limites, no uno.** Cada handler `show` acepta 80 caracteres Y la
  coleccion completa acepta maximo 10 handlers (~800 chars por respuesta).
  Como se trocea linea por linea, una lista con una opcion por renglon gasta
  un handler por renglon y revienta el segundo limite con texto corto.
  `build_show_handlers` compacta renglones cuando no caben.
- **No se recorta el texto.** Si ni compactado cabe, truena a proposito:
  pasarse de 800 significa que el prompt dejo al agente soltar una parrafada, y
  eso se arregla en el prompt (o reintentando comprimido, del lado del fork).
  Recortando se taparia el bug y el lead leeria media respuesta.
- **Emojis.** Algunos emojis modernos llegan a WhatsApp como `?`;
  `adapt_text_for_kommo` los cambia por equivalentes seguros y quita lo que
  queda fuera del BMP. Tambien colapsa `**negritas**` de markdown a `*`, que es
  lo que WhatsApp si renderiza.

### app/usage.py y app/notifications.py
Telemetria y errores. `log_usage` escribe a `logs/usage.jsonl` Y a la tabla
`usage_logs` (con tokens del LLM en `usage_metadata` — esa es la metrica para
vigilar costo y "ruido" de contexto por turno). `notify_error` hoy es print;
el hook ya esta inyectado donde debe, solo falta conectarle un canal real.

---

## scripts/

- `setup_app_db.py` — migraciones idempotentes de LAS TABLAS PROPIAS
  (`contact_profiles`, `conversation_profiles`, `usage_logs`), versionadas en
  `agent_schema_migrations`. Agregar columna = nueva entrada en `MIGRATIONS`,
  nunca editar una aplicada.
- `setup_postgres_memory.py` — crea las tablas del checkpointer de LangGraph.

## Tests (scripts planos, sin pytest: `.venv/bin/python -m tests.test_X`)

Se corren como modulo, no como archivo suelto: asi resuelven `app/` y `core/`
desde la raiz del repo.

| Test | Que congela |
|---|---|
| `test_qualification.py` | pesos, umbrales y politicas de handoff (criterio comercial) |
| `test_signal_detection.py` | regex de senales + merge de patrones custom |
| `test_safety_prompt.py` | que `build_agent` SIEMPRE anteponga el safety prompt |
| `test_context_middleware.py` | inyeccion de contexto sin tocar historial |
| `test_settings.py` | fail-fast al arrancar sin API key del provider |
| `test_llm_timeout.py` | que todo proveedor reciba timeout por default |
| `test_empty_response_retry.py` | que un vacio de Gemini nunca se persista |
| `test_tool_claim_guard.py` | que no se afirme un hecho sin la tool que lo respalda |
| `test_kommo_client.py` | los dos limites de Kommo y la adaptacion de texto |
| `test_abuse_detection.py` | insultos/jailbreak/ruido sin marcar mensajes normales |
| `test_agrupado_mensajes.py` | agrupado por lead, sin mezclar ni arrastrar texto |
| `test_date_normalization.py` | fechas relativas resueltas en codigo |

Los scripts de `scripts/smoke/` (`test_llm/agent/memory/runner.py`) son de humo
manual: llaman LLM y BD reales y cuestan tokens. Todo lo de `tests/` corre sin
red ni BD.

## Deuda conocida (a proposito, ver docs/plan_de_trabajo.md)

Pool de conexiones Postgres, `logging` en vez de print, fail-fast de settings
al arrancar, locks sin limite en runner, summarization del historial largo
(`SummarizationMiddleware` ya viene en la version instalada de langchain),
cola/worker para rafagas, escritura a Kommo, seguimientos automaticos.
Congelados deliberadamente hasta que el primer piloto este en produccion.
