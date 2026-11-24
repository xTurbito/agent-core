"""Punto de arranque. Une el runner del cliente (app) con la API (core).

main -> app -> core   (la flecha de dependencia)
"""

from app.bootstrap import build_runner
from app.channels.kommo import create_kommo_router
from app.notifications import notify_error
from app.usage import log_usage
from core.api import create_app
from core.error_reporting import with_error_tracking
from core.logging_config import configurar_logging
from core.settings import settings

# Antes de construir nada: si algo loguea al arrancar, ya sale formateado.
configurar_logging(settings.log_level)

runner = build_runner()

app = create_app(
    runner,
    on_error=with_error_tracking(notify_error, settings.sentry_dsn),
    log_usage=log_usage,
)
app.include_router(create_kommo_router(runner))
