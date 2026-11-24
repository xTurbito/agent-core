# Capas de instrucciones: quien manda en cada regla

Lee esto antes de cambiar una regla de comportamiento del agente en cualquier
fork. Viene de BEA (fork de salon, noviembre de 2026): casi todos los casos de
"el agente se atora" o "se marea" vinieron de dos capas diciendole al modelo
cosas distintas.

## Las capas

Al modelo le llegan ordenes desde varios lugares y las lee todas juntas:

| Capa | Donde vive | Que debe tener |
|---|---|---|
| System prompt | `app/prompts/` (+ lo que inyecta `ContextInjectionMiddleware` por turno) | El embudo del negocio (cuando ofrecer, cuando cobrar, cuando escalar) y el tono |
| Docstrings de las tools | `app/tools/*.py` | Que hace la tool y que significa cada campo o status. Nada de reglas de venta |
| Datos del catalogo | El sistema externo del fork (Agenda, CRM, ERP) cuando entrega instrucciones por producto o servicio | Solo lo propio de ese producto: preparacion, exclusiones, horarios fijos, que preguntar para elegir variante |
| Guards | middleware en `app/business/` y `core/guards.py` | Lo que tiene consecuencia real (precio, cita, pago) y no puede depender de que el modelo obedezca |

## Reglas

1. **Una regla general vive una sola vez**, en el prompt. Si se copia en el
   catalogo, cambiarla obliga a editar decenas de filas y alguna queda vieja.
2. **Una docstring es prompt.** El modelo la lee como instruccion. Si una tool
   dice "no avances hasta resolver el paso anterior", eso gana aunque el
   prompt diga lo contrario. Revisa las docstrings cuando cambies el prompt.
3. **No asumas que el prompt gana.** Ante dos capas que se contradicen, el
   modelo obedece cualquiera de las dos, y cambia entre corridas.
4. **Ninguna capa puede pedir algo imposible.** Ejemplo real: "solo cuando ya
   eligio un horario, consulta la agenda" (para elegir hay que ofrecer), o
   "valida el pago" cuando el agente no ve pagos.
5. **Precios y fechas no van en texto libre.** Salen de los campos
   estructurados (precio base, promociones con vigencia). Un precio escrito a
   mano se desfasa y una fecha escrita obliga al modelo a calcularla.
6. **Una pregunta por mensaje.** Ninguna capa debe pedir "y ahi mismo pregunta
   tambien X": la persona contesta una y la otra se pierde.
7. **Lo que tiene consecuencia real se fuerza con un guard**, no solo con
   texto (cerrar una venta sin decir el precio, agendar fuera del horario,
   afirmar un pago).
8. **Las etiquetas del CRM son contrato.** Si una automatizacion externa
   (seguimiento, reactivacion) se dispara por un tag, ponerlo bien es tan
   importante como la respuesta. Un tag que depende de un "match unico" en la
   busqueda falla cuando el catalogo crece.

## Como cambiar una regla sin romper nada

1. Busca la regla en las tres capas (`grep` en prompt y tools, consulta de
   solo lectura al catalogo) antes de editar.
2. Decide quien es el dueno con la tabla de arriba; quita las copias.
3. Prueba el cambio de datos en una copia local del catalogo, con ida y vuelta
   (aplicar y revertir deben tocar las mismas filas).
4. Corre evals del caso que toca, antes y despues. Para comparar contra el
   codigo de main usa `git worktree`, no `git stash`.
5. Verifica en produccion despues de aplicar; un cambio sin COMMIT no se ve
   hasta que alguien lo revisa.

## Costo de probar con el LLM real

Cada llamada manda el prompt completo mas historial y resultados de tools. En
BEA eran 20 a 25 mil tokens por llamada (~60% ya en cache del proveedor). Corre
solo los casos que toca el cambio.

Para la voz del agente (ejemplos en vez de adjetivos, guards que no pegan texto
fijo, version del prompt detras de una variable) ver `docs/voz-con-ejemplos.md`.
