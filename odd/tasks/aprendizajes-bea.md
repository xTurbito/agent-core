# aprendizajes-bea

Objetivo: llevar a agent-core los aprendizajes genericos de BEA (fork de salon) para que cualquier fork, incluido Volt, los tenga. Rama: feat/aprendizajes-bea (worktree ../agent-core-aprendizajes, desde main 5c72cd9). Delivery: ask-on-risk; push y PR los decide Miguel. Tests: scripts planos con assert (`.venv/bin/python -m tests.test_X`).

## Specs

- S1. Llevar a agent-core los aprendizajes genericos de BEA, sin nada del salon ni de Kommo especifico del negocio (regla de CLAUDE.md: core/ nunca importa de app/).
- S2. No chocar con el trabajo sin commit de ../agent-core-eventos (feat/agent-events: agent_events.py y handoff_events.py). Lo que toca main.py, app/bootstrap.py o la lista de middleware de build_agent va despues o coordinado.
- S3. Cada unidad con sus tests. Agent-core es un contrato que otros forks consumen: revision independiente antes de pedir el merge.
- S4. El modelo de respaldo cubre toda llamada al LLM, no solo la del agente: en BEA, el 2026-11-26, el resumidor y el SummarizationMiddleware solo usaban el principal y fallaron cuando la key llego a su tope.
- S5. Arnes de evals generico para que cada fork, incluido el agente nuevo, nazca midiendo: correr casos de varios turnos contra el agente armado igual que en produccion, reglas puras (respuesta vacia y rubrica de tono) que el fork extiende con las suyas, y la opcion de correr con el modelo de respaldo como principal.

## Tasks

| ID | Specs | Unidad | Ruta | Estado | Evidencia |
|---|---|---|---|---|---|
| T1 | S1, S3 | U1 fechas: weekday_name calculado en Python, "del <año>", months_between, business_zone | inline | hecho | f7c5448 |
| T2 | S1, S3 | U5 /chat rechaza session_id vacio con 422 | inline | hecho | 3663a9b |
| T3 | S1, S3 | U4 bateria offline + CI + pyproject + requirements-dev | inline | hecho | 7470c4d |
| T4 | S1, S3 | U7 doc generica: capas de instrucciones, voz con ejemplos, guards sin texto fijo | inline | hecho | c5ff440, 101e684 |
| T5 | S1, S2, S3 | U2 LLM robusto: reintento por respuesta cortada, modelo de respaldo, openrouter | inline | hecho | 5130aba, bbb4909, 5d8c059 |
| T6 | S1, S2, S3 | U3 logging y redaccion de secretos | inline | hecho | 196a433 |
| T7 | S1, S2, S3 | U6 monitoring: decidir si se acepta depender de usage_logs | por decidir | pendiente | |
| T8 | S1, S3, S4 | U8 el respaldo cubre toda llamada al LLM (agente, SummarizationMiddleware y las de app/) | inline | hecho | e90b12a (RED: ImportError de invocar_con_respaldo; GREEN 22+1 tests) |
| T9 | S3 | Revision independiente de T1-T6 (4 auditores en paralelo, fase 1 solo lectura) | delegado (regla de revision de CLAUDE.md) | hecho: fase 1 y correcciones (L7, L9) | d5a7341..2b1e71b |
| T10 | S3, S5 | U9 arnes de evals: core/evals.py puro + scripts/evals del fork + test sin red | inline | hecho, PR #11 (apilado sobre #10) | fefe92b + 388ea93 (RED/GREEN en cada uno; bateria 23/23) |

## Log

- L1 (2026-11-22, Miguel): "y si todas esas decisiones que han beneficiado tanto a BEA como Volt, que se vayan a agent-core como tal porfavor" / "todos los aprendizajes pues"
- L2: Mapeo read-only. merge-base d0325b7; runner.py, guards.py y memory.py ya son identicos. agent.py upstream usa CRLF (comparar con --ignore-cr-at-eol). Ya lo tienen: abuse_detection, agrupado_mensajes, bounded_cache y webhooks. Upstream va adelante en scripts/chat_cli.py y en tests (tool_claim_guard, bounded_cache, agent_runner). core/tracing.py de upstream usa settings.langfuse_*, que no existe, y nadie lo llama. Los scripts/evals de BEA importan guards del negocio: solo se lleva la idea del arnes, no el codigo.
- L3: Se pregunto a la sesion de Volt si ../agent-core-eventos es suyo, antes de tocar main.py y bootstrap.
- L4 (2026-11-26, Miguel): "simon, vamos con eso". Se refiere a cerrar lo hecho (doc al dia y revision independiente de los 9 commits) y despues meter el punto 1 como unidad nueva: "El respaldo tiene que cubrir todas las llamadas al LLM, no solo al agente".
- L5: Puesta al dia. T1-T6 ya estaban hechos en 9 commits (f7c5448..5d8c059), ya subidos a origin. El diff suma 1622 lineas en 26 archivos, por arriba del presupuesto de ~400: antes del PR hay que decidir la estrategia de cadena (ask-on-risk).
- L6: T8 hecho en e90b12a. En agent-core la unica llamada suelta era el resumidor (SummarizationMiddleware solo existe en BEA). construir_llms pasa a core/llm.py; invocar_con_respaldo cubre error y respuesta vacia.
- L7: T9 fase 1 (4 auditores en paralelo, solo lectura, sobre main..5d8c059). Ninguno encontro bloqueantes de codigo. Verificado por el parent:
  - Calidad: ID de lead real en tests/test_logging_config.py:80,85.
  - Calidad: contenido de salon en docs/voz-con-ejemplos.md.
  - Bugs: "del 10" se toma como año 2010 y se confirma.
  - Bugs: months_between negativo da -2 en vez de -1.
  - Bugs: la redaccion de secret no ve una URL anidada en otro valor.
  - Bugs: el reintento por respuesta cortada solo ve finish_reason "length" (Gemini manda MAX_TOKENS y Anthropic stop_reason max_tokens).
  - Seguridad: Sentry manda las variables locales de los frames.
  - Seguridad: el CI no declara permissions.
  - Rendimiento: el respaldo conserva los reintentos de la libreria (~2 min por llamada).
  - Calidad propone una cadena de 6 PRs. Fase 2 (correcciones) espera el OK de Miguel.
- L8 (2026-11-26, Miguel): "simon, vas con eso". Se aprueba el recorte: corregir 1, 2, 3, 5, 7 y 9 antes de crear el fork nuevo, en 3 PRs. Lo demas (4, 6, 8) queda para despues.
- L9: Correcciones hechas, cada una con RED observado antes del fix:
  - d5a7341: lead_id inventado en el test de logging.
  - 54fae66: "del" solo toma un año de 4 digitos.
  - 0859ba8: la respuesta cortada se detecta tambien en Gemini y Anthropic.
  - 8ce8a97: Sentry ya no manda las variables locales.
  - 56ab50a: el respaldo no reintenta por su cuenta.
  - 2b1e71b: docs sin contenido del salon.
  Bateria 22/22. core/agent.py es CRLF: editarlo con open() de Python lo pasa a LF y el diff se infla a todo el archivo (se corrigio con fixup).
- L10: Pasada de recorte. Con 3 PRs, los tamaños serian ~1000 (codigo), ~580 (logging) y ~380 (docs). La regla de ~400 pide 6: A1 CI+fechas+session_id ~344, A2 LLM (5130aba+fixups+cortada) ~470, A3 respaldo en llamadas sueltas ~200, B1 logging ~320, B2 Sentry ~250, C docs ~380. Falta que Miguel elija.
- L11: Correccion de premisa. Los 9 commits originales ya estaban en main por el PR #9 (merge del 2026-11-24); el main local del worktree estaba viejo. Lo que falta en main es T8 mas las correcciones (~351 lineas), asi que va en un solo PR. Las 5 ramas apiladas que se habian subido se borraron con el OK de Miguel. Se agrega `permissions: contents: read` al CI (hallazgo 8), que eran dos lineas.
- L12 (2026-11-26, Miguel): "simon, vas con eso", sobre meter el arnes de evals como la siguiente unidad antes del agente nuevo. Va en la rama feat/evals-arnes, apilada sobre #10 porque usa construir_llms de core/llm.py.
- L13: T10 en fefe92b. Agrega core/evals.py (puro), armar_agente en app/bootstrap.py (lo comparten build_runner y los evals), scripts/evals con runner y casos de ejemplo, y docs/evals.md. Se verifico con build_agent real y un modelo falso de LangChain: las llamadas y model_name se capturan bien. Revision independiente en curso.
- L14: Revision independiente de fefe92b: sin bloqueantes. Correcciones en 388ea93, cada una con su test: contesto sale del mensaje final, un error del modelo queda como violacion y el caso se corta, conteo de emojis (bandera, ZWJ y keycap valen uno; °©™ no cuentan), 'Buenas noticias' no es saludo, el ? de una URL no es pregunta, corridas mayor que 0. Se agrego el test del primario caido con el respaldo contestando, sobre build_agent real. Falta el OK de Miguel para subir la rama y abrir el PR apilado sobre #10.
