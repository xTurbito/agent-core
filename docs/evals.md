# Evals del agente

Los tests de `tests/` prueban el codigo sin LLM. Los evals prueban **al agente**:
mandan conversaciones de varios turnos al modelo real, con el prompt, las tools y
el armado de produccion, y revisan reglas sobre lo que contesto. Cuestan tokens y
no corren en CI.

```bash
.venv/bin/python -m scripts.evals.correr                  # todos los casos, una corrida
.venv/bin/python -m scripts.evals.correr disponibilidad 3 # un caso, 3 corridas
.venv/bin/python -m scripts.evals.correr --con-respaldo   # el respaldo como unico modelo
.venv/bin/python -m scripts.evals.correr --json salida.json
```

Sale con 1 si alguna regla se rompio. El resumen dice, por caso, llamadas al
modelo por turno, segundos por turno, violaciones y que modelo contesto.

## Piezas

| Pieza | Donde | Quien la cambia |
|---|---|---|
| Arnes (`correr_caso`, `evaluar`, reglas base) | `core/evals.py` | nadie por fork |
| Armado del agente | `armar_agente` en `app/bootstrap.py` | el fork; produccion y evals lo comparten |
| Casos | `scripts/evals/casos.py` | el fork |
| Reglas de negocio y tool de escalamiento | `REGLAS` y `TOOL_ESCALAR` en `scripts/evals/correr.py` | el fork |

Una regla es una funcion que recibe la lista de `Turno` y regresa `Violacion`.
Las reglas base son `regla_sin_respuesta_vacia` y `reglas_de_tono` (no saludar a
media conversacion, maximo un emoji y, si le pasas la tool de escalamiento, no
abrir pregunta al escalar y cerrar con pregunta cuando no escala).

## Reglas de trabajo

- **Corre la linea base antes de cambiar el prompt**, con los mismos casos que vas
  a usar despues. Si no, no sabes si mejoraste o solo cambiaste.
- **Mide tambien el respaldo** (`--con-respaldo`). Un modelo de respaldo que nunca
  se corrio contra los casos no es un respaldo: en un fork en produccion, el dia
  que el primario se quedo sin saldo, el respaldo contesto todos los turnos y
  escalo de mas porque nadie lo habia medido.
- **Los casos salen de produccion**, sobre todo de las conversaciones que salieron
  mal. Los de `scripts/evals/casos.py` son solo ejemplos.
- **El mismo contexto que produccion.** Si el agente recibe contexto por turno
  (fecha, catalogo, perfil), los evals tienen que recibirlo igual; por eso el
  agente se arma con `armar_agente`. Sin el, una regla que depende del contexto
  se ve rota cuando no lo esta.
- **Una corrida por caso es una muestra chica.** Repite los casos que fallan
  antes de concluir.
- **El guion es fijo**: el usuario no reacciona a lo que conteste el agente.
  Sirve para comparar corridas, no para simular a una persona.
