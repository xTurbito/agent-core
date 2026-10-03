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

logger = logging.getLogger(__name__)

ErrorHandler = Callable[[Exception, dict[str, Any]], None]

_initialized = False


def with_error_tracking(handler: ErrorHandler, dsn: str | None) -> ErrorHandler:
    """Devuelve un ErrorHandler que llama a `handler` y, si hay DSN
    configurado, tambien reporta el error a un servicio externo.
    """
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
    )
    _initialized = True
