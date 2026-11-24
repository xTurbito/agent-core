# aprendizajes-bea

Objetivo: llevar a agent-core los aprendizajes genericos de BEA (fork de salon) para que cualquier fork, incluido Volt, los tenga. Rama: feat/aprendizajes-bea (worktree ../agent-core-aprendizajes, desde main 5c72cd9). Delivery: ask-on-risk; push y PR los decide Miguel. Tests: scripts planos con assert (`.venv/bin/python -m tests.test_X`).

## Specs

- S1. Llevar a agent-core los aprendizajes genericos de BEA, sin nada del salon ni de Kommo especifico del negocio (regla de CLAUDE.md: core/ nunca importa de app/).
- S2. No chocar con el trabajo sin commit de ../agent-core-eventos (feat/agent-events: agent_events.py y handoff_events.py). Lo que toca main.py, app/bootstrap.py o la lista de middleware de build_agent va despues o coordinado.
- S3. Cada unidad con sus tests. Agent-core es un contrato que otros forks consumen: revision independiente antes de pedir el merge.

## Tasks

| ID | Specs | Unidad | Ruta | Estado | Evidencia |
|---|---|---|---|---|---|
| T1 | S1, S3 | U1 fechas: weekday_name calculado en Python, "del <año>", months_between, business_zone (BEA 0cc8142, a8380e6, 5f9a869, cc33329) | inline | en curso | |
| T2 | S1, S3 | U5 /chat rechaza session_id vacio con 422 (BEA 5dafeb2) | inline | pendiente | |
| T3 | S1, S3 | U4 bateria offline (scripts/correr_bateria.py) + CI + pyproject + requirements-dev (BEA 88ae56f, 962885a) | inline | pendiente | |
| T4 | S1, S3 | U7 doc generica: capas de instrucciones (la docstring de una tool es prompt; una regla general vive una vez en el prompt) | inline | pendiente | |
| T5 | S1, S2, S3 | U2 LLM robusto: reintento por respuesta cortada, modelo de respaldo, max_tokens 4096, timeout, provider openrouter (BEA 91a0e73, 042b1f5, 1f6e737, f0a4ae3) | por decidir | esperando coordinacion (toca bootstrap y build_agent) | |
| T6 | S1, S2, S3 | U3 logging y redaccion de secretos (BEA 15af910, b821938 y otros) | por decidir | esperando coordinacion (toca main.py) | |
| T7 | S1, S2, S3 | U6 monitoring (BEA 44e7cda): decidir si se acepta depender de usage_logs | por decidir | pendiente | |

## Log

- L1 (2026-11-22, Miguel): "y si todas esas decisiones que han beneficiado tanto a BEA como Volt, que se vayan a agent-core como tal porfavor" / "todos los aprendizajes pues"
- L2: Mapeo read-only. merge-base d0325b7; runner.py, guards.py y memory.py ya son identicos. agent.py upstream usa CRLF (comparar con --ignore-cr-at-eol). Ya lo tienen: abuse_detection, agrupado_mensajes, bounded_cache y webhooks. Upstream va adelante en scripts/chat_cli.py y en tests (tool_claim_guard, bounded_cache, agent_runner). core/tracing.py de upstream usa settings.langfuse_*, que no existe, y nadie lo llama. Los scripts/evals de BEA importan guards del negocio: solo se lleva la idea del arnes, no el codigo.
- L3: Se pregunto a la sesion de Volt si ../agent-core-eventos es suyo, antes de tocar main.py y bootstrap.
