# Plan de trabajo — agent-core

Contexto: este repo es la base generica (`agent-core`) para clientes reales
atendidos por agentes de IA via Kommo/WhatsApp. **Ya no esta en fase de
piloto: dos forks estan en produccion real**, verificados end-to-end
(2026-10-03):

- **Volt** (`ChatBicimoto`, tienda de bicis electricas) — Kommo + catalogo
  Shopify (`app/integrations/shopify_client.py`), `https://agente.ar-solutions.com.mx`.
- **Bea** (`ChatBotTheBrowStudio`, salon de belleza) — Kommo + agenda real via
  `AgendaTheBrowStudio` (.NET), `https://agente.thebrowstudio.mx`.
- **Clinica psicologica** (WhatsApp directo) — todavia NO arranco. Sigue
  siendo el tercer cliente objetivo; `core/webhooks.py` ya trae HMAC generico
  listo para cuando se construya ese canal.

Regla de oro que se mantiene: `core/` generico y reutilizable, `app/`
especifico por fork, `core` nunca importa de `app`. Antes de mover algo a
`core` preguntar: "¿los 3 clientes lo necesitan tal cual?".

---

## Fase 0 — Seguridad basica ✅ CERRADA

- [x] Autenticacion en `/chat` — Bearer `CHAT_API_KEY`, fail-closed.
- [x] Secreto del webhook de Kommo (`?secret=`), fail-closed, dedup por
      `message_id`.
- [x] Limite de tamano de mensaje (Pydantic + check manual en Kommo).

## Fase 1 — Robustez del core

- [x] Tests de negocio y de seguridad (`test_qualification.py`,
      `test_signal_detection.py`, `test_safety_prompt.py`, + 9 mas, ver
      `docs/arquitectura.md`).
- [x] Versiones fijadas en `requirements.txt`.
- [x] **Fail-fast en `core/settings.py`** — ya lanza `RuntimeError` si falta la
      API key del provider activo. Verificado en `core/settings.py:59-61`.
- [ ] **Pool de conexiones Postgres** en `app/memory/profiles.py` — sigue
      abriendo una conexion nueva por query. Verificado: no hay pool en el
      codigo real. *(deuda, no bloquea produccion actual)*
- [ ] **Logging real** — `app/channels/kommo.py` e
      `integrations/kommo_client.py` siguen con `print()`, no `logging`.
      Verificado contando ocurrencias reales.
- [ ] **`AgentRunner._locks` sin limite** (`core/runner.py:44-60`) — un
      `Lock()` por `session_id` historico, nunca se libera. Mismo patron de
      cache acotado que ya usa el dedup de Kommo.

## Fase 2 — Piloto ✅ SUPERADA (ya es produccion real, no "primer piloto")

Todo lo que este bloque pedia esta hecho y verificado contra trafico real en
Volt y Bea: prompt de calificacion activa, extraccion a `important_data`,
FAQ precargada, escritura a Kommo (`update_lead_fields`/`move_lead_stage`/
`pause_lead_ai`), deploy con Dokploy, `MEMORY_KIND=postgres`, prueba
end-to-end contra Kommo real. La whitelist de canary (`KOMMO_ALLOWED_LEAD_IDS`)
ya no aplica como gate — ambos forks corren sin ella.

## Fase 2.5 — Observabilidad/alerting ✅ CERRADA (2026-10-03)

3 capas, cada una con audiencia distinta (decision completa en memoria
engram, proyecto `chatbicimoto`/`chatbotthebrowstudio`):

- [x] **Sentry** — errores de codigo dentro de la app, push a celular.
      `core/error_reporting.py` (`with_error_tracking()`), verificado
      end-to-end en los 3 repos.
- [x] **Langfuse self-hosted** (`https://langfuse.ar-solutions.com.mx`) —
      trazas de LLM (prompt, tools, latencia) compartidas entre Volt y Bea.
      `core/tracing.py` (`build_callbacks()`) existe y funciona, **pero sigue
      SIN COMMITEAR en `agent-core`** (solo en el working tree local) — primer
      pendiente a resolver, si no el proximo fork no lo hereda.
- [x] **UptimeRobot** — `/health` de Volt y Bea en verde, monitoreando la
      version desplegada real (healthcheck profundo, verifica Postgres).

## Fase 3 — Siguientes clientes y escala

- [x] **Poner al dia `ChatBicimoto`** — sync de `core/` hecho, migrado al
      patron `channels/business/integrations`, ya no es el placeholder de
      "clinica dental".
- [x] **Integracion Shopify (bicis)** — `app/integrations/shopify_client.py`
      ya existe y esta en uso real por Volt.
- [ ] **Canal WhatsApp directo (clinica psicologica)** — todavia no se
      construyo `app/channels/whatsapp.py`. `core/webhooks.py` (HMAC
      generico, firma `X-Hub-Signature-256` de Meta) ya esta listo para
      cuando arranque este fork.
- [ ] **Seguimientos automaticos a leads frios** — scheduler sobre
      `conversation_profiles` estancadas, con reglas anti-spam. Sin empezar
      en ningun fork (verificado: no hay codigo de scheduler ni en Volt ni en
      Bea).
- [ ] **`SummarizationMiddleware` para historial largo** — sigue sin
      implementarse (ver Fase 4, issue #3: NO reimplementar desde cero, usar
      el que ya trae LangChain).
- [ ] **Cola/worker para rafagas** — sigue sin empezar; mismo
      bloqueo de worker unico de uvicorn que ya documenta `CLAUDE.md`.
- [ ] **Politica de datos sensibles para la clinica psicologica** — cifrado
      en reposo y retencion. Bloqueada hasta que ese fork exista.
- [ ] **Secretos mas alla de `.env`** con 2-3 clientes simultaneos en
      produccion.

## Fase 4 (en curso) — Generalizar guards y reglas de prompt entre forks

Volt (10 guards) y Bea (9 guards) acumularon logica de perfilamiento/
razonamiento totalmente duplicada, sin compartir mecanismo. Analisis de
Codex (2026-10-07, solo lectura; memoria completa en engram proyecto
`agent-core` bajo "Analisis Codex: generalizacion de guards Volt/Bea hacia
agent-core") confirmo que ningun guard se copia literal: casi todos mezclan
un mecanismo generico ("un claim requiere evidencia de tool antes de
afirmarse", "un valor de una tool debe respaldar el argumento de otra") con
contenido de negocio especifico (regex, copy, tools concretas).

**Hallazgo critico, prioridad 0**: `core/guards.py` ya diverge entre forks.
Bea quedo identico byte a byte al base de `agent-core`, pero Volt le agrego
`backing_tools: dict[str,str]`, `FalseDenialGuardMiddleware` y
`ForbiddenPatternGuardMiddleware` directo en su fork, con firma incompatible,
sin subir nada a `agent-core`. No generalizar copiando la version de Volt tal
cual — rompe Bea.

**Antes de extraer cualquier mecanismo**, resolver las contradicciones reales
entre prompt y guard que el analisis encontro en ambos forks (si se
generalizan tal cual, el bug local se congela en la base compartida):
- Volt: `perfil_guard.py` exige terreno/velocidad/peso pero el workflow real
  solo pide familia/km/presupuesto (el NUDGE que se inyecta al LLM queda
  desactualizado, aunque el chequeo real ya es correcto — riesgo bajo, texto
  pendiente de corregir); `familia_sin_entrevista_guard.py` no respetaba la
  excepcion UTM que el prompt si permite — **CONFIRMADO Y CERRADO en el fork
  Volt (2026-10-18)**: el detector tiene firma `(texto, messages)` y el hint
  de UTM vive en el `system_message`, fuera de su alcance; se resolvio con un
  override en `_GuardFamiliaSinEntrevistaMiddleware` (el nivel que si tiene
  `request.system_message`), reusando `MARCADOR_HINT_UTM` ya existente en
  `UtmHintGuardMiddleware`. Sin test hasta ahora (ver abajo); `test` nuevo
  pendiente de agregar. **Este fix vive en `app/` de Volt, todavia NO subio a
  `agent-core`** — primero se prueba localizado, se generaliza cuando el
  mecanismo este maduro (ver orden de trabajo).
  `UtmHintGuardMiddleware` sigue con el defecto complementario: acepta
  cualquier tool-call sin validar cual, asi que no detecta cuando la llamada
  que si hizo el LLM fue la incorrecta.
- Bea: `FrasesProhibidasGuardMiddleware` puede bloquear el propio menu exacto
  del prompt; la FAQ autoriza dar direccion/pago pero escalamiento los lista
  como no disponibles; la politica de simbolos choca con los emojis exigidos
  en la plantilla de ubicacion. **Pendiente de auditar con la misma
  metodologia que Volt** (ver subseccion de abajo).

**Hallazgo nuevo de la auditoria de Volt (2026-10-18), antes de generalizar
nada**: de los 13 guards registrados en `app/bootstrap.py`, **5 no tenian
NINGUN test** (`cierre_prematuro_guard`, `familia_sin_entrevista_guard`,
`presupuesto_comparativa_guard`, `saludo_duplicado_guard`, `tono_guard`) — se
detecto buscando por nombre de FUNCION contra `tests/`, no por nombre de
archivo (buscar por archivo dio falso negativo). El bug de UTM arriba vivio
sin detectarse desde el 2026-10-05 justamente porque su guard no tenia test.
Subir a `core` un mecanismo sin su test local primero es subir el riesgo, no
solo el codigo.

Orden de trabajo sugerido (issues reales en `agent-core`, estado 2026-10-07,
actualizado 2026-10-18):

- [ ] **Commitear `core/tracing.py`** (Langfuse) — cabo suelto de Fase 2.5,
      ver arriba.
- [x] **Volt: CERRADO** — auditoria + tests de consistencia prompt↔guard.
      Los 5 guards sin test quedaron cerrados con fix+test+doc, guard por
      guard: `familia_sin_entrevista_guard` (bug real, excepcion de hint UTM
      que el prompt permitia y el guard no respetaba), `cierre_prematuro_guard`
      (bug real, la jugada de apartado-con-adelanto no debia exigir perfil
      completo como la compra real), `presupuesto_comparativa_guard`,
      `saludo_duplicado_guard` y `tono_guard` (estos tres sin bug, solo
      faltaba test). Documentados en `docs/arquitectura.md` de Volt con sus
      limitaciones conocidas. Faltan documentar ahi los otros 8
      guards/middlewares que ya tenian test antes de esta auditoria
      (`perfil_guard`, `utm_hint_guard`, `promesa_guard`, `vehiculo_guard`,
      y los genericos de `core/guards.py` que Volt configura).
- [ ] **Bea**: pendiente, auditoria delegada a sesion nueva con el mismo
      metodo (prompt del encargo guardado en engram, proyecto
      `chatbicimoto`).
- [x] **Prototipado en Volt** (commit `7ad36e9`): ningun guard de Volt/Bea
      interceptaba la TOOL-CALL antes de que se ejecute — todos tienen
      `if tool_calls: return response` y solo validan el texto final. Para
      lectura (catalogo, FAQ) no importa; para una tool con efecto real
      (`generar_link_de_compra`, `agendar_cita`) es el hueco real: el patron
      de la industria (guardrails pre+post-LLM) pide un gate ANTES de
      ejecutar la tool. `HandleProvenanceGuardMiddleware`
      (`app/business/handle_provenance_guard.py` en Volt) usa el hook
      `AgentMiddleware.wrap_tool_call` (existe en LangChain, no hizo falta
      nada nuevo del framework): bloquea `generar_link_de_compra` devolviendo
      un `ToolMessage` de error directo, sin llamar al handler, si el handle
      no aparecio en un resultado real de catalogo en la conversacion.
      Verificado contra el grafo real de `create_agent`: con el guard
      bloqueando, la funcion de la tool nunca se invoca.
      **Pendiente para generalizar a `core/guards.py`**: es el mismo
      mecanismo generico que ya pedia #6 (provenance: valor de tool fuente
      respalda argumento de tool consumidora, validado ANTES del side
      effect) pero ahora con wrap_tool_call en vez de wrap_model_call.
      Extraer `ToolCallProvenanceGuardMiddleware` generico (fork aporta que
      tool-call vigilar, que args tienen provenance, y de que tools previas)
      una vez que exista un segundo caso real (Bea: `agendar_cita` es la
      candidata obvia) para no generalizar de un solo ejemplo.
- [x] **Prototipado en Volt** (commit `94e3916`): `scripts/smoke/golden_set.py`
      -- 2 escenarios por ahora, conversaciones REALES de produccion (via
      Postgres readonly), replay contra `build_runner()` real (los 14
      guards activos), reusando los detectores de los guards como chequeo
      sobre la respuesta final. Sin umbral estadistico (no corre N veces por
      escenario, cada uno corre una vez); el valor es detectar regresiones
      obvias entre un cambio y el siguiente, no certificar calidad.
      **Ya encontro un bug real en su primera corrida**: un lead sin hint de
      UTM que solo da marca/uso filtraba precio en el 100% de las corridas
      iniciales con el guard de un solo reintento -- ver el fix de
      `familia_sin_entrevista_guard` arriba. Pendiente: crecer de 2 a mas
      escenarios, y decidir si vale la pena el umbral de regresion con
      multiples corridas por escenario (mas costo en tokens/tiempo) antes de
      generalizar el patron a otros forks.
- [ ] **#4 — ampliar**, no solo "¿se llamo la tool?": helper estructurado de
      tool-interactions (scope turno/conversacion, `tool_call_id`, parsing de
      resultado, provenance). Es la dependencia comun de casi todos los guards.
- [ ] **#5 — confirma, corrige alcance**: generalizar `ToolClaimGuardMiddleware`
      con evidence predicates, multiples tools de respaldo, scope,
      claims negativos y `skip_if` — construido sobre #4, NO sobre la version
      ya divergida de Volt.
- [ ] **#6 — corrige y acota**: el problema real es "provenance" generico
      (valor de tool fuente debe respaldar argumento de tool consumidora,
      validado ANTES del side effect). `core/date_normalization.py` ya esta
      resuelto, no duplicar.
- [ ] **Issue nuevo**: grounding de valores estructurados devueltos por una
      tool (ej. horarios de `consultar_disponibilidad`), extension de #5.
- [ ] **Issue nuevo**: `ConditionalActionGuardMiddleware` + secuencias
      fallback (cubre hint UTM, perfil completo sin busqueda, avance forzado
      a disponibilidad/escalamiento).
- [ ] **#3 — confirma, no reimplementar**: LangChain ya trae
      `SummarizationMiddleware`; lo reusable es una factory con config por
      defecto + plantilla de summary prompt, documentando que evidencia no
      puede depender de texto resumido.
- [ ] Guards menores, baja prioridad: `ForbiddenTextGuardMiddleware`,
      `UniqueMarkerGuardMiddleware`, `ConversationBudgetGuardMiddleware`.
      `filler_guard.py` de Volt se queda en `app/` — hoy ningun otro fork lo
      necesita ("¿los 3 clientes lo necesitan tal cual?" da no).
- [ ] **#7** (bug, no generalizacion): `DuplicatedContentGuardMiddleware` no
      agarra duplicados parafraseados — corregir independiente de esta fase.
- [ ] **#2** (independiente): LLM-judge de calidad de conversaciones
      (Bea + Volt) para detectar fallas reales en produccion.
- [ ] **#1** (independiente): metodologia de fases para implementar/mejorar
      agentes, aplicable a Bea, Volt y forks nuevos.

**Convencion de documentacion pendiente de redactar en `docs/arquitectura.md`**:
plantilla de docstring de 9 campos (invariante, fallo observado, evidencia
requerida, scope, punto de intercepcion, excepciones, limitaciones, politica
de retry) para formalizar la regla ya existente "el prompt pide, el guardian
obliga". No centralizar en `core` el playbook de cierre de un fork concreto
(el de Bea depende de `consultar_disponibilidad`/`agendar_cita`, el de Volt de
`generar_link_de_compra`): eso es negocio de cada `app/`. **Corregido
2026-10-17**: esto NO aplica al oficio de vender generico — ver
"Replanteamiento: base de venta compartida" abajo.

### Replanteamiento: base de venta compartida (2026-10-17)

El analisis de Codex estaba scopeado a **guards**; trato los system prompts
solo como fuente de contradicciones contra esos guards, no como activo a
generalizar. Por eso la conclusion sobre playbooks de venta quedo en una
linea, y quedo mal fundamentada.

**La justificacion original no se sostiene.** Un bloque de prompt compartido
es una constante string, no un import: `BASE_SAFETY_PROMPT` ya vive en
`core/agent.py:18` y se compone en `core/agent.py:113`
(`f"{BASE_SAFETY_PROMPT}\n\n{system_prompt}"`), sin importar nada de `app/`,
y ya tiene un test que lo vigila (`tests/test_safety_prompt.py`). La regla
`core/ nunca importa de app/` no esta en juego para texto de prompt.

**El diagnostico real** (comparando los dos prompts de produccion, ~800
lineas cada uno): Bea es un vendedor con una base de conocimiento pegada;
Volt es una base de conocimiento con reglas de venta pegadas. Hoy `core`
aporta UN solo bloque compartido y esta usado solo para seguridad, asi que
todo el oficio de vender se reinventa por fork. Consecuencias medidas:

- Volt se autodefine en su linea 14 como que "**recibe consultas**" — el
  sesgo de respondedor esta escrito en su identidad.
- Volt no tiene bloque de criterio propio. Su equivalente mas cercano
  ("orientas a la compra sin presionar") es una restriccion, no un rasgo.
- La entrevista de Volt (familia → nombre → km → presupuesto) son los
  argumentos de `buscar_vehiculos`, no movidas de venta: nunca pregunta que
  le cuesta al lead su problema actual.
- Volt no tiene autoauditoria, ni ratio de habla, ni presupuesto de mensajes;
  nada fuerza el avance al cierre durante la charla.
- Ante "lo voy a pensar" Volt retrocede ("dale calma, no presiones"); Bea
  vende a traves de la objecion.
- **Drift ya observable**: `EJEMPLOS DE TONO` de Volt le ENSEÑA a decir "Con
  gusto te ayudo" (su linea 106), frase que Bea tiene prohibida por sonar a
  call center (su linea 129). Dos forks del mismo core con instrucciones
  opuestas sobre la misma frase.

**Criterio de reparto** (aplicando "¿los 3 clientes lo necesitan tal cual?"):

| Va a `core/` (oficio de vender, agnostico al negocio) | Se queda en `app/` |
|---|---|
| Identidad anti-asistente ("no eres un buscador de informacion, guias una decision") | La accion de cierre concreta y sus tools |
| Criterio propio: recomienda y tambien desaconseja | Catalogo, precios, legal, garantia |
| "No necesitas la venta" (credibilidad por poder perderla) | Registro regional y modismos |
| Autoauditoria cada N turnos contra sonar generico | Lista literal de frases prohibidas (la categoria es generica, las frases son regionales) |
| Ratio de habla y presupuesto de mensajes / avance forzado | Tabla de vocabulario de marca |
| SPIN: situacion → problema → implicacion → beneficio | Simbolos/emojis permitidos por canal |
| Objecion ≠ cosa rota ("un 'lo voy a pensar' no se repara, se vende") | FAQ del negocio |
| Recomienda no des menu / anuncia no pidas permiso / señal de compra deja de informar | |
| Permiso de decir que no (una por mensaje, nunca dos) | |
| Anti-loop: si pide lo mismo por tercera vez, cambia de movida | |

**Mecanismo propuesto**: segundo bloque en `core`, **opt-in** (no
incondicional como safety: la clinica psicologica no quiere "señal de compra,
deja de informar"), compuesto ANTES del prompt del fork para que cada `app/`
pueda especializar, con test que lo vigile igual que
`tests/test_safety_prompt.py`. Mismo patron ya probado, sin conceptos nuevos.

**Precondicion que no se puede saltar**: el primer item del checklist de
arriba (auditoria de consistencia prompt↔guard) sigue bloqueando esto. Caso
concreto: si se sube la lista de frases prohibidas de Bea a `core`, se sube
con ella el bug de que `FrasesProhibidasGuardMiddleware` puede bloquear el
propio menu exacto del prompt.

Items nuevos:

- [ ] **Quick win, independiente de todo lo demas**: quitar "Con gusto te
      ayudo" de `EJEMPLOS DE TONO` en Volt. Es drift puro y no depende de
      ninguna generalizacion.
- [ ] **Redactar el bloque de venta compartido**, extrayendo de lo ya probado
      en produccion en el prompt de Bea, segun la tabla de reparto de arriba.
      Depende de la auditoria prompt↔guard.
- [ ] **Decidir la forma del opt-in** en `build_agent` (flag booleano vs
      lista de bloques componibles) antes de escribir el bloque.
- [ ] **Test de presencia/orden** del bloque de venta, espejando
      `tests/test_safety_prompt.py`.
- [ ] **Portar el bloque a Volt** y medir contra conversaciones reales de la
      base de produccion (no solo contra tests): el criterio de exito es que
      deje de sonar a respondedor, y eso solo se ve en transcripciones.

**Limite honesto, no es problema de prompt**: Bea cierra sola
(`agendar_cita`), Volt siempre termina en "un asesor confirma" porque no
tiene tool de agenda ni fuente de plazo de entrega. El prompt puede hacer que
Volt califique y venda mucho mejor; no puede hacer que cierre hasta que exista
el wiring de AgendaSystem en su fork. Precio y link de compra si los tiene
(Shopify real), eso no es limitante.

---

## Fase 5 — Monitoreo centralizado (iniciativa separada, sin empezar)

Miguel quiere un centro de monitoreo en VPS para ver en tiempo real el
rendimiento de TODOS sus agentes (no solo Bea/Volt), mas alla de
Sentry/Langfuse/UptimeRobot por repo. Hay un repo creado (`infra-monitoring`
en GitHub) pero sin trabajo registrado todavia. No depende de la Fase 4.

---

## Como usar este documento

Checklist vivo — marca `[x]` conforme cierres y agrega lo que surja. Verifica
contra el codigo real antes de marcar algo como hecho (no confies en el texto
viejo de este archivo: se encontraron varios items ya resueltos que seguian
sin marcar, y varios marcados "post-piloto" que ya no aplican porque el
piloto termino).
