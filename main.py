"""Punto de arranque. Une el runner del cliente (app) con la API (core).

main -> app -> core   (la flecha de dependencia)
"""

from app.bootstrap import build_runner
from app.channels.kommo import create_kommo_router
from app.notifications import notify_error
from app.usage import log_usage
from core.api import create_app

runner = build_runner()

app = create_app(runner, on_error=notify_error, log_usage=log_usage)
app.include_router(create_kommo_router(runner))
