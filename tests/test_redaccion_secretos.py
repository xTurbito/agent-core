"""El secreto del webhook (?secret=...) no puede quedar en los logs ni en Sentry.

Kommo no firma el webhook, asi que el secreto viaja en la URL. uvicorn escribe cada
request en el logger "uvicorn.access" con la query string, y Sentry guarda la URL del
request. Contrato: el valor se reemplaza por "***" y el resto de la linea no cambia.

Se prueba con el AccessFormatter REAL de uvicorn y en el orden de produccion (uvicorn
configura su logging primero y luego la app llama a configurar_logging). Un redactor que
junte mensaje y args rompe ese formatter, que desarma record.args en 5 campos.

Correr con: .venv/bin/python -m tests.test_redaccion_secretos
"""

import contextlib
import io
import logging
import logging.config
from unittest.mock import patch

import uvicorn.config

from core import error_reporting
from core.error_reporting import ocultar_parametros_en_evento
from core.logging_config import PARAMETROS_URL_SENSIBLES, configurar_logging

SECRETO = "s3cr3t-abc123"

assert "secret" in PARAMETROS_URL_SENSIBLES


def salida_de_uvicorn_access(ruta: str) -> str:
    """Una linea del access log de uvicorn, formateada por su formatter real."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)  # lo primero que hace uvicorn
        configurar_logging("INFO")  # despues, la app
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "10.0.0.5:51234", "POST", ruta, "1.1", 200
        )
    return buffer.getvalue()


# --- uvicorn.access: el valor sale oculto y los 5 campos siguen saliendo ---
linea = salida_de_uvicorn_access(f"/kommo/incoming-message?secret={SECRETO}")
assert SECRETO not in linea, f"el secreto salio en el access log: {linea!r}"
assert "secret=***" in linea, linea
for campo in ("10.0.0.5:51234", "POST", "/kommo/incoming-message", "1.1", "200"):
    assert campo in linea, f"se perdio el campo {campo!r}: {linea!r}"
print("OK: el access log de uvicorn oculta el secreto y conserva los 5 campos")

# --- el secreto no es el unico parametro, ni siempre el primero ---
linea = salida_de_uvicorn_access(f"/kommo/incoming-message?x=1&secret={SECRETO}&y=2")
assert SECRETO not in linea
assert "x=1" in linea and "y=2" in linea and "secret=***" in linea, linea
print("OK: solo se oculta el valor del secreto; los demas parametros quedan")

# --- sin secreto, la linea no cambia ---
linea = salida_de_uvicorn_access("/kommo/widget-request?lead_id=123")
assert "lead_id=123" in linea and "***" not in linea, linea
print("OK: una URL sin secreto sale igual")

# --- root logger: un mensaje que lleva la URL tambien sale oculto ---
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    configurar_logging("INFO")
    logging.getLogger("app.channels.kommo").info(
        "request a https://bot.example/kommo/incoming-message?secret=%s", SECRETO
    )
salida = buffer.getvalue()
assert SECRETO not in salida and "secret=***" in salida, salida
print("OK: el root logger oculta el secreto en el mensaje ya formateado")


# --- Sentry: el evento llega con la URL y la query string, sin el valor ---
def evento():
    return {
        "request": {
            "url": f"https://bot.example/kommo/incoming-message?secret={SECRETO}&x=1",
            # Sentry guarda la query string SIN el "?", el parametro va al inicio
            "query_string": f"secret={SECRETO}&x=1",
            "method": "POST",
        },
        "breadcrumbs": {
            "values": [{"message": f"POST /kommo/incoming-message?secret={SECRETO} 200"}]
        },
        "extra": {"url": f"/kommo/incoming-message?x=1&secret={SECRETO}"},
    }


oculto = ocultar_parametros_en_evento(evento(), PARAMETROS_URL_SENSIBLES)
assert SECRETO not in repr(oculto), f"el secreto sigue en el evento: {oculto!r}"
assert oculto["request"]["query_string"] == "secret=***&x=1", oculto["request"]
assert oculto["request"]["url"].endswith("?secret=***&x=1"), oculto["request"]
assert oculto["request"]["method"] == "POST"
assert "x=1" in oculto["extra"]["url"]
print("OK: el evento de Sentry oculta el secreto en url, query_string, breadcrumbs y extras")

sin_secreto = {"request": {"url": "https://bot.example/health", "query_string": ""}}
assert ocultar_parametros_en_evento(sin_secreto, PARAMETROS_URL_SENSIBLES) == sin_secreto
print("OK: un evento sin secreto no cambia")

# --- Sentry realmente usa el ocultado: sentry_sdk.init recibe before_send ---
with patch("sentry_sdk.init") as init:
    error_reporting._initialized = False
    error_reporting._init_sentry("https://clave@o0.ingest.sentry.io/1")
    error_reporting._initialized = False
kwargs = init.call_args.kwargs
assert callable(kwargs.get("before_send")), "sentry_sdk.init no recibio before_send"
filtrado = kwargs["before_send"](evento(), {})
assert filtrado is not None and SECRETO not in repr(filtrado)
print("OK: sentry_sdk.init arranca con un before_send que oculta el secreto")

# ===== Bordes del mismo mecanismo =====


def salida_de(emitir) -> str:
    """Corre `emitir()` con la configuracion de uvicorn y la de la app, y regresa lo escrito."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
        configurar_logging("INFO")
        emitir()
    return buffer.getvalue()


# --- el nombre del parametro puede venir percent-encoded: Starlette lo decodifica y autentica ---
linea = salida_de_uvicorn_access(f"/kommo/incoming-message?se%63ret={SECRETO}&x=1")
assert SECRETO not in linea, f"se%63ret evadio el filtro: {linea!r}"
assert "x=1" in linea and "***" in linea, linea
linea = salida_de_uvicorn_access(f"/kommo/incoming-message?SeCrEt={SECRETO}")
assert SECRETO not in linea, linea
print("OK: el nombre del parametro se compara decodificado y sin distinguir mayusculas")

# --- uvicorn.error tambien: mensaje con argumentos y traceback ---
log_error = lambda: logging.getLogger("uvicorn.error")  # noqa: E731

salida = salida_de(lambda: log_error().error("request secret=%s", SECRETO))
assert SECRETO not in salida and "secret=***" in salida, salida
print("OK: uvicorn.error oculta el secreto que llega como argumento")


def traceback_con_la_url():
    try:
        raise ValueError(f"fallo en https://bot.example/kommo/incoming-message?secret={SECRETO}")
    except ValueError:
        log_error().exception("Exception in ASGI application")


salida = salida_de(traceback_con_la_url)
assert SECRETO not in salida, f"el traceback filtro el secreto: {salida!r}"
assert "ValueError" in salida and "Exception in ASGI application" in salida, salida
print("OK: el traceback de uvicorn.error sale sin el secreto y sigue siendo legible")

# --- Sentry: una clave sensible oculta su valor, sea del tipo que sea ---
for valor in (["a", SECRETO], {"valor": SECRETO}, 12345, None):
    oculto = ocultar_parametros_en_evento({"extra": {"secret": valor}}, PARAMETROS_URL_SENSIBLES)
    assert oculto == {"extra": {"secret": "***"}}, oculto
print("OK: Sentry oculta TODO el valor bajo una clave sensible, de cualquier tipo")

# --- before_send nunca lanza ni devuelve el evento sin limpiar ---
ciclico = {"request": {"url": f"https://bot.example/k?secret={SECRETO}"}}
ciclico["yo_mismo"] = ciclico
filtrado = error_reporting._antes_de_enviar(ciclico, {})
assert filtrado is not None and SECRETO not in repr(filtrado), "evento ciclico sin limpiar"

profundo: dict = {"url": f"/k?secret={SECRETO}"}
for _ in range(500):
    profundo = {"hijo": profundo}
filtrado = error_reporting._antes_de_enviar(profundo, {})
assert filtrado is not None and SECRETO not in repr(filtrado), "evento profundo sin limpiar"
print("OK: before_send aguanta eventos ciclicos o muy profundos sin perder el secreto")

print("\nTodas las pruebas de redaccion de secretos pasaron.")
