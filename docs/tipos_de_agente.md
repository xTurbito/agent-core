# Tipos de agente: atención, venta y consultoría

`agent-core` proporciona capacidades reutilizables para construir agentes conversacionales, pero el rol del agente pertenece al negocio de cada fork. Un agente de atención, un agente comercial y un agente consultor pueden compartir infraestructura sin compartir objetivos, políticas ni métricas.

## Clasificación rápida

| Tipo | Objetivo principal | Cuándo actúa | Resultado esperado |
| --- | --- | --- | --- |
| Asistente de atención reactivo | Resolver una solicitud entrante y orientar el siguiente paso. | Cuando la persona escribe. | Duda resuelta, acción operativa o transferencia. |
| Asistente comercial reactivo | Resolver y producir avance comercial dentro del turno. | Cuando la persona escribe. | Cita, cotización, calificación o siguiente paso. |
| Sales Agent proactivo | Gestionar la continuidad comercial y la conversión. | Durante el turno y después de periodos de inactividad autorizados. | Conversación recuperada, cita, venta o decisión correcta de no contactar. |
| Agente consultor | Diagnosticar y recomendar la alternativa más adecuada. | Durante una exploración guiada; puede incluir seguimiento autorizado. | Recomendación justificable, incluso cuando implica no comprar. |
| Agente híbrido | Combinar diagnóstico consultivo con un objetivo comercial explícito. | Según la política del negocio. | Recomendación adecuada y avance comercial sin sacrificar el criterio. |

## Estado actual de la base

La base actual está orientada principalmente a agentes reactivos: recibe un mensaje, ejecuta herramientas, genera una respuesta y puede transferir el caso. Un fork puede añadir comportamiento comercial dentro del turno, pero eso no lo convierte por sí solo en un Sales Agent proactivo.

La diferencia no es únicamente el tono del prompt:

- un agente reactivo espera una entrada;
- un Sales Agent evalúa continuidad, programa revisiones y mide resultados;
- un agente consultor prioriza el diagnóstico correcto sobre la conversión inmediata.

## Separación arquitectónica

### Capacidades potencialmente compartidas

Estas capacidades pueden pertenecer a `core/` cuando varios forks demuestren que necesitan el mismo contrato:

- ejecución del agente y herramientas;
- memoria y contexto inyectado por turno;
- historial canónico de eventos;
- decisiones estructuradas;
- programación y bandeja de salida persistente;
- revalidación antes de efectos externos;
- idempotencia, auditoría y trazabilidad;
- infraestructura de evaluaciones.

### Responsabilidades del fork

Estas decisiones permanecen en `app/` porque dependen del giro:

- objetivo del agente;
- acciones permitidas;
- reglas de elegibilidad y detención;
- Playbook y conocimiento comercial;
- herramientas e integraciones operativas;
- criterios de transferencia humana;
- tono y límites de marca;
- definición de éxito y métricas.

## Sales Agent

Un Sales Agent no es un chatbot con instrucciones más persuasivas. Necesita capacidades operativas adicionales:

1. Observar el estado completo de la conversación.
2. Reconocer intención, objeciones, avance y señales de detención.
3. Elegir entre responder, esperar, programar, omitir o transferir.
4. Revalidar el estado antes de ejecutar una acción.
5. Registrar la estrategia y evidencia utilizadas.
6. Relacionar sus decisiones con resultados posteriores.

La conversión no justifica contactar siempre. Esperar, no intervenir o recomendar una alternativa distinta deben ser resultados válidos.

## Agente consultor

Un agente consultor prioriza comprender el problema y recomendar con fundamento. Debe poder:

- explorar necesidades y restricciones;
- explicar alternativas y consecuencias;
- reconocer cuándo falta información;
- recomendar no comprar o posponer una decisión;
- transferir casos que requieren criterio profesional;
- justificar la recomendación con evidencia disponible.

Puede contribuir a una venta, pero la venta es consecuencia de una recomendación adecuada, no la única salida aceptable.

## Caso BEA

BEA actualmente funciona como un **asistente comercial reactivo**: responde dudas, consulta información operativa, ayuda a agendar y orienta la conversación hacia una cita.

El objetivo propuesto es convertirla en un **Sales Agent proactivo con comportamiento consultivo y límites explícitos**. Eso requiere continuidad entre turnos, decisiones estructuradas, seguimiento autorizado, revalidación y medición; no solamente cambios de redacción.

## Otros giros

Un fork de otro giro no debe heredar automáticamente el objetivo comercial de BEA. Por ejemplo, un producto que ayuda a diagnosticar una necesidad técnica puede requerir un agente consultor o híbrido, aunque reutilice memoria, herramientas, auditoría y entrega.

El tipo definitivo debe establecerse después de revisar:

- qué resultado busca el negocio;
- qué decisiones puede tomar el agente;
- qué consecuencias tiene una recomendación incorrecta;
- cuándo debe intervenir una persona;
- qué señales permiten medir éxito y daño.

## Regla de extracción hacia `core/`

No se debe crear un framework universal a partir de un único caso. Una capacidad se extrae desde un fork hacia `core/` cuando:

1. varios clientes la necesitan con el mismo contrato;
2. no contiene reglas, datos ni vocabulario de un negocio;
3. la política variable puede inyectarse desde `app/`;
4. existen pruebas genéricas que no dependen de un cliente;
5. la extracción reduce duplicación sin ocultar diferencias importantes.

Hasta entonces, la implementación vive en el fork que demostró la necesidad. Esta regla evita convertir decisiones específicas de venta, salud, belleza o soporte en supuestas abstracciones universales.

## Decisión práctica

La plataforma compartida debe modelar capacidades, no imponer una personalidad comercial. Cada fork compone esas capacidades para construir un asistente reactivo, un Sales Agent, un agente consultor o un híbrido según su dominio.
