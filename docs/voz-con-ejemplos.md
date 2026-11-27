# Voz con ejemplos y guards que no rompen el tono

Lee esto antes de reescribir el prompt de un fork o de cambiar como suena el
agente. Viene de un fork en produccion (noviembre de 2026): el prompt bajo de 62
mil a 21 mil caracteres, la voz se definio con ejemplos y dejo de sonar a bot.
Este core no trae esos guards ni esos evals; aqui va la leccion, no el codigo.

Complementa `docs/capas-de-instrucciones.md`, que explica quien manda en cada
regla (prompt, docstrings, catalogo, guards).

## 1. La voz se define con ejemplos, no con adjetivos

"Cercana, elegante, consultiva" no le dice nada al modelo, y tampoco al dueno
del negocio: cada quien entiende otra cosa por "amable". Lo que funciono:

1. **Proponer 5 mensajes reales** para situaciones tipicas y validarlos con quien
   conoce el negocio antes de tocar el prompt: primer mensaje con info y costo,
   solo saluda, pide cita, "lo voy a pensar" y un caso que escala.
2. **Revisar los ejemplos contra lo que el sistema puede cumplir.** "Te escribo
   manana" ensena a prometer algo que el bot no hace si no manda mensajes
   salientes. "Te aparto sin compromiso" choca con una regla de negocio si
   apartar requiere anticipo.
3. **Placeholders en lugar de datos.** El modelo copia los ejemplos casi literal:
   un precio o una fecha de promo dentro de un ejemplo se sigue diciendo cuando ya
   no es cierto. Escribe `[precio de la tool de catalogo]`. Lo mismo aplica a los
   beneficios: "te dura todo el ano" es un dato que ninguna tool dio.
4. **Variar el arranque.** Si todos los ejemplos abren con "¡Hola!", el modelo
   saluda en cada turno. Pon al menos un ejemplo de media conversacion, sin
   saludo, y di explicitamente que no repita las frases de los ejemplos.
5. **Cubrir las objeciones que deciden la venta** ("esta caro", "¿duele?").
6. **Ejemplos malos reales**, marcados como "asi NO", sacados de produccion.
7. **En el prompt van 3 a 5 ejemplos.** Con mas, el modelo tiende a copiar el
   ultimo; los demas sirven como rubrica de evals. Aun con pocos, el modelo copia
   el saludo de un ejemplo palabra por palabra: varialo o acepta que todos los
   clientes reciban el mismo.

Fuentes: [Anthropic, multishot prompting](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/multishot-prompting),
[OpenAI, prompt engineering](https://help.openai.com/en/articles/6654000-prompt-engineering-guide).

## 2. Revisa lo que el canal le hace al texto

`adapt_text_for_kommo` (`app/integrations/kommo_client.py`) cambia o borra lo
que queda fuera del BMP (casi todos los emojis modernos) y los renglones vacios.
En el fork de referencia la voz aprobada usaba un emoji que nunca le llego a
nadie. Antes de aprobar una voz, pasa los ejemplos por el adaptador del canal.
Una regla de formato que el canal anula ("separa con un renglon en blanco") no
sirve.

## 3. Un guard que pega texto fijo arma mensajes Frankenstein

El patron que nos mordio: el modelo escribe su respuesta y un guard le
**inserta** una frase fija (la promo literal, la ubicacion con su emoji). Salen
dos voces en el mismo mensaje, con el bloque en un lugar raro. En la linea base
paso en 3 de 9 casos, incluso antes de saber que servicio queria el cliente.

Lo que lo arreglo:

1. El guard **verifica**, no escribe. Si falta el dato, hace **un** reintento
   con un aviso que trae el dato exacto: "te falta la promo; incluyela con tus
   palabras, en tu tono, antes de tu pregunta final; usa exactamente estos
   montos; la promo es: <frase>".
2. **El reintento se acepta solo si es seguro**: dice el dato, conserva los
   montos que ya traia el borrador, no inventa otros montos ni porcentajes y no
   trae la marca interna de la fuente ("Promocion vigente:"). Si no, entra la
   frase literal como red de seguridad.
3. **"Ya se dijo" se detecta por los datos, no por el texto literal.** Cuenta si
   aparece literal o si estan todos sus montos. El porcentaje puede omitirse solo
   si la promo trae dos o mas montos, y un porcentaje que no es de la promo la
   invalida. Si sigues buscando la frase literal, todo lo que dependa de eso se
   rompe en cuanto el modelo la parafrasea: el guard la vuelve a pedir cada turno.
4. **Cuidado con los montos que coinciden.** Un precio que nadie pidio y que es
   igual a un monto de la promo (el precio base de "de $1,000 a $800") sigue
   siendo un precio no pedido. Solo se descuenta como promo si la promo completa
   esta en el texto.
5. **Quitar la insercion no basta.** Si el prompt, el aviso de otro guard o la
   docstring de una tool siguen diciendo "di la frase literal", el modelo copia
   a mano lo que antes pegaba el guard. Quita "literal" de cada capa que le habla
   al modelo.
6. **El costo es real.** Una llamada extra al modelo en los turnos donde falta el
   dato. En el fork de referencia el promedio paso de 2.3 a 2.8 llamadas por
   turno y la latencia subio cerca de 34%. Mide antes de prenderlo.

## 4. Los guards tambien le hablan al modelo

- **Las frases prohibidas se mueven junto con la voz.** Si apruebas "con todo
  gusto" y un guard lo prohibe, el guard reescribe la voz nueva sin avisar.
  Pasa cada ejemplo aprobado por el guard de frases en un test. Si una regla
  del guard viene de una decision anterior (por ejemplo, no abrir con "Hola, que
  gusto"), cambia el ejemplo antes que deshacer la decision.
- **Los avisos de los guards citan el prompt.** "El prompt pide 20-30 palabras"
  en un nudge queda mintiendo en cuanto el prompt cambia. Revisa los nudges en el
  mismo cambio.

## 5. Antes de recortar el prompt, inventario por regla

Recortar por seccion borra cosas que importan. Clasifica **cada regla** en un
solo bucket, con evidencia `archivo:linea`:

| Bucket | Que hacer |
|---|---|
| QUEDA | regla general que solo el prompt puede llevar; una sola vez |
| GUARD/TOOL | ya la hace cumplir el codigo o la docstring de una tool: sale del prompt |
| DATOS | dato del negocio (precios, duraciones, politicas): va a la fuente |
| SOBRA | obsoleta o contradicha |
| VOZ | adjetivo de tono: la reemplazan los ejemplos |

Lo mas valioso son las **contradicciones vivas entre el prompt y el codigo**. En
el fork de referencia el prompt decia "escalar no te calla, puedes seguir
resolviendo dudas" y la tool pausa la IA al escalar. En produccion el bot
escalaba y en el mismo mensaje abria una pregunta que ya nadie iba a contestar.
Leyendo solo el prompt, eso no se ve. Lo mismo con un flujo que el canal ya
resuelve: si al llegar un archivo el codigo escala solo, pedirlo Y escalar en el
mismo mensaje deja una pregunta abierta con la IA pausada.

Despues de escribir el prompt nuevo, **compara regla por regla contra el viejo
las que ningun guard cubre**. En el fork de referencia se habian caido "si
rechazo dos pares de horarios, pregunta que rango le sirve" y "si el precio esta
en duda, escala". Busca cada tema en todo el prompt antes de cerrarlo: una regla
escrita en dos lugares acaba contradiciendose.

## 6. Version del prompt detras de una variable

Conviene que el prompt nuevo viva junto al viejo y se elija con una variable
(por ejemplo `PROMPT_VERSION`; este core todavia no trae ese selector):

- El default es el prompt viejo: hacer merge no cambia nada hasta que se prende
  la variable.
- Un valor que no existe truena al arrancar, nunca cae en otra version en
  silencio.
- Si registras un hash de configuracion por turno, que salga del prompt
  **activo**. Asi se comparan las dos versiones en produccion con los mismos
  datos.
- Volver atras es cambiar la variable y redesplegar, sin revertir codigo.
- Ojo: si alguien ya puso la variable en el servidor, el merge prende la version
  nueva en el siguiente deploy. Revisa el entorno antes de asumir que el default
  te protege.
- Los tests que leen el texto del prompt importan la version que prueban, no el
  "prompt activo", y la bateria fija la variable al default. Si no, el resultado
  depende del `.env` de quien la corre.

## 7. Mide el tono, no solo las reglas

Los evals de reglas (precio antes de cerrar, sin respuesta vacia) no ven si el
bot suena seco. Agrega una rubrica que se revise con codigo:

- no abre con formulas secas ("Va", "Retomo donde ibamos");
- no vuelve a saludar a media conversacion;
- maximo un emoji;
- si no escala, cierra con una pregunta o un siguiente paso;
- si escala, no abre una pregunta.

Lo que el codigo no mide (si reacciona a lo que dijo el cliente, si suena
calido, el orden del mensaje) se califica leyendo las respuestas contra los
ejemplos aprobados.

Reglas de trabajo:

- **Corre la linea base con el prompt actual antes de cambiar nada**, con los
  mismos casos que vas a usar despues. En el fork de referencia la linea base
  mostro que el problema principal era el guard que pegaba la promo, no el modelo.
- **Los evals tienen que recibir el mismo contexto de turno que produccion**
  (fecha de hoy, catalogo, horarios, perfil del cliente). Sin el, una regla que
  depende del contexto se ve rota cuando no lo esta.
- **Una corrida por caso es una muestra chica.** Repite los casos que fallan
  antes de concluir.

## Resultado en el fork de referencia

Mismos 9 casos, mismo modelo, con contexto de produccion:

| | Prompt viejo | Prompt nuevo |
|---|---|---|
| Promo pegada como bloque | 3 de 9 | 0 de 9 |
| Violaciones de reglas | 0 | 0 |
| Mensajes que reaccionan al cliente | pocos | todos |
| Tamano del prompt | 62 mil caracteres | 21 mil |
| Segundos por turno | 10.5 | 14.1 |
