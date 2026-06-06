"""Punto de arranque. Une el runner del cliente (app) con la API (core).

main -> app -> core   (la flecha de dependencia)
"""

from app.bootstrap import build_runner
from core.api import create_app

app = create_app(build_runner())
