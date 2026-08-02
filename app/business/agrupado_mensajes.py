"""Junta mensajes seguidos del mismo lead en un solo turno.

En WhatsApp la gente escribe entrecortado: manda "Pero que es?" y un segundo
despues "Que se hace?". Cada mensaje entrante disparaba su propia generacion,
asi que recibia dos respuestas completas casi identicas, cada una explicando lo
mismo desde cero (visto en produccion: dos ciclos con 1.3 segundos de
diferencia). Ademas se pagaban dos llamadas al LLM por la misma pregunta.

La idea es simple: al llegar un mensaje se espera un momento por si viene otro.
Si llega, el turno viejo se descarta y el nuevo responde por los dos juntos.
"""

import asyncio
from collections import OrderedDict


class AgrupadorDeMensajes:
    """Espera una ventana corta antes de dejar responder.

    El estado vive en memoria del proceso, igual que el cache de dedup y el de
    flood: con UN worker de uvicorn alcanza (ver CLAUDE.md). Con dos workers
    los mensajes de un mismo lead podrian caer en procesos distintos y no
    agruparse, que es el mismo motivo por el que ya corremos con un worker.
    """

    def __init__(self, ventana_segundos: float, max_claves: int = 2000, dormir=None):
        self._ventana = ventana_segundos
        self._max_claves = max_claves
        self._dormir = dormir or asyncio.sleep
        self._textos: OrderedDict[str, list[str]] = OrderedDict()
        self._turnos: dict[str, int] = {}

    async def agrupar(self, clave: str, texto: str) -> str | None:
        """Devuelve el texto juntado, o None si este turno hay que descartarlo.

        None significa que mientras se esperaba llego otro mensaje del mismo
        lead: ese mensaje mas nuevo es el que va a responder por los dos, asi
        que este turno se calla para no duplicar la respuesta.
        """
        self._textos.setdefault(clave, []).append(texto)
        self._textos.move_to_end(clave)
        self._recortar()

        turno = self._turnos.get(clave, 0) + 1
        self._turnos[clave] = turno

        await self._dormir(self._ventana)

        if self._turnos.get(clave) != turno:
            return None

        textos = self._textos.pop(clave, [])
        self._turnos.pop(clave, None)

        return "\n".join(textos)

    def pendientes(self) -> int:
        """Cuantos leads tienen texto esperando. Solo para pruebas y depuracion."""
        return len(self._textos)

    def _recortar(self) -> None:
        while len(self._textos) > self._max_claves:
            vieja, _ = self._textos.popitem(last=False)
            self._turnos.pop(vieja, None)
