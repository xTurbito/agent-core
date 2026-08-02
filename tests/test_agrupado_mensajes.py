"""Pruebas del agrupado de mensajes seguidos.

En WhatsApp la gente escribe entrecortado: "Pero que es?" y un segundo despues
"Que se hace?". Sin agrupar, cada mensaje generaba su propia respuesta y la
clienta recibia dos parrafos completos casi identicos (conversacion A38736,
dos ciclos con 1.3 segundos de diferencia).
"""

import asyncio

from app.business.agrupado_mensajes import AgrupadorDeMensajes

VENTANA = 0.05


def correr(corutina):
    return asyncio.run(corutina)


# Caso 1: un mensaje solo se responde tal cual.
agrupador = AgrupadorDeMensajes(VENTANA)
assert correr(agrupador.agrupar("lead-1", "Hola")) == "Hola"
print("OK: un mensaje solo pasa sin cambios")


# Caso 2: dos mensajes seguidos = UNA sola respuesta con los dos textos.
async def dos_seguidos():
    agrupador = AgrupadorDeMensajes(VENTANA)

    async def segundo():
        await asyncio.sleep(VENTANA / 5)
        return await agrupador.agrupar("lead-1", "Que se hace?")

    return await asyncio.gather(
        agrupador.agrupar("lead-1", "Pero que es?"),
        segundo(),
    )


primero, segundo = correr(dos_seguidos())
assert primero is None, primero
assert segundo == "Pero que es?\nQue se hace?", segundo
print("OK: dos mensajes seguidos se juntan en una sola respuesta")


# Caso 3: leads distintos no se mezclan (seria filtrar conversaciones ajenas).
async def dos_leads():
    agrupador = AgrupadorDeMensajes(VENTANA)
    return await asyncio.gather(
        agrupador.agrupar("lead-1", "soy la uno"),
        agrupador.agrupar("lead-2", "soy la dos"),
    )


uno, dos = correr(dos_leads())
assert uno == "soy la uno", uno
assert dos == "soy la dos", dos
print("OK: mensajes de leads distintos no se mezclan")


# Caso 4: el buffer se limpia; el siguiente mensaje no arrastra el anterior.
async def dos_turnos():
    agrupador = AgrupadorDeMensajes(VENTANA)
    primero = await agrupador.agrupar("lead-1", "primer turno")
    segundo = await agrupador.agrupar("lead-1", "segundo turno")
    return primero, segundo, agrupador.pendientes()


primero, segundo, pendientes = correr(dos_turnos())
assert primero == "primer turno"
assert segundo == "segundo turno", segundo
assert pendientes == 0, pendientes
print("OK: el buffer se limpia entre turnos y no arrastra texto viejo")


# Caso 5: el estado en memoria no crece sin limite (mismo riesgo que los otros
# caches del canal: un worker, se resetea al reiniciar uvicorn).
async def muchos_leads():
    agrupador = AgrupadorDeMensajes(VENTANA, max_claves=10)
    for indice in range(50):
        await agrupador.agrupar(f"lead-{indice}", "hola")
    return agrupador.pendientes()


assert correr(muchos_leads()) <= 10
print("OK: el estado del agrupador esta acotado")

print("\nTodas las pruebas de agrupado de mensajes pasaron.")
