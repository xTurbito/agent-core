"""Reporte de errores reales a un servicio externo, mas alla de los logs.

Envuelve un ErrorHandler existente (el que ya persiste a su propio log o
base de datos) y le agrega el reporte a un servicio de error tracking
externo, sin reemplazar lo que ya hacia. Sin DSN configurado, el wrapper
solo llama al handler original: un fallo al reportar hacia afuera nunca
debe tapar ni romper lo que el handler ya hacia.

Deliberadamente no manda datos personales por default (send_default_pii
queda en False) ni habilita rastreo de performance (traces_sample_rate en
0) -- ese alcance es solo captura de errores, nada mas.
"""

import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote

from core.logging_config import OCULTO, PARAMETROS_URL_SENSIBLES, ocultar_parametros

logger = logging.getLogger(__name__)

ErrorHandler = Callable[[Exception, dict[str, Any]], None]

_initialized = False


PROFUNDIDAD_MAXIMA = 40
CICLO = "<ciclo>"
DEMASIADO_PROFUNDO = "<demasiado profundo>"


def ocultar_parametros_en_evento(evento: Any, parametros: tuple[str, ...]) -> Any:
    """Oculta el valor de los parametros sensibles en todo el evento de Sentry.

    Sentry guarda la URL del request, su query string (sin el "?"), breadcrumbs y
    extras; el secreto del webhook viaja en la URL, asi que se recorre el
    evento entero. Si el parametro llega como llave de un dict se oculta TODO su
    valor, sea del tipo que sea. Un ciclo o una estructura muy profunda se corta con
    un marcador en lugar de lanzar: lo que no se puede limpiar no se devuelve.
    """
    sensibles = {p.lower() for p in parametros}
    return _ocultar(evento, parametros, sensibles, 0, set())


def _ocultar(
    evento: Any,
    parametros: tuple[str, ...],
    sensibles: set[str],
    nivel: int,
    camino: set[int],
) -> Any:
    if isinstance(evento, str):
        return ocultar_parametros(evento, parametros)
    if not isinstance(evento, dict | list | tuple):
        return evento
    if nivel >= PROFUNDIDAD_MAXIMA:
        return DEMASIADO_PROFUNDO
    if id(evento) in camino:
        return CICLO
    camino = camino | {id(evento)}
    if isinstance(evento, dict):
        return {
            k: OCULTO
            if isinstance(k, str) and unquote(k).lower() in sensibles
            else _ocultar(v, parametros, sensibles, nivel + 1, camino)
            for k, v in evento.items()
        }
    limpio = [_ocultar(v, parametros, sensibles, nivel + 1, camino) for v in evento]
    return tuple(limpio) if isinstance(evento, tuple) else limpio


EVENTO_OMITIDO = {
    "message": "Evento omitido: no se pudo ocultar los parametros sensibles",
    "level": "error",
}


def _antes_de_enviar(evento: Any, _hint: Any) -> Any:
    """before_send de Sentry. Nunca lanza (si lanza, Sentry pierde el evento) y nunca
    devuelve el evento sin limpiar: si falla, manda uno minimo y seguro."""
    try:
        return ocultar_parametros_en_evento(evento, PARAMETROS_URL_SENSIBLES)
    except Exception:
        logger.exception("No se pudo ocultar el evento de Sentry; se manda uno minimo")
        return dict(EVENTO_OMITIDO)


def with_error_tracking(handler: ErrorHandler, dsn: str | None) -> ErrorHandler:
    if dsn:
        _init_sentry(dsn)

    def reportar(error: Exception, context: dict[str, Any]) -> None:
        handler(error, context)

        if not dsn:
            return

        try:
            import sentry_sdk

            with sentry_sdk.new_scope() as scope:
                scope.set_context("app", context)
                sentry_sdk.capture_exception(error)
        except Exception:
            logger.exception("Fallo al mandar el error al servicio de error tracking")

    return reportar


def _init_sentry(dsn: str) -> None:
    global _initialized
    if _initialized:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=_antes_de_enviar,
    )
    _initialized = True
