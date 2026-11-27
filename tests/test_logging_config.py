"""Fija el CONTRATO DE PRIVACIDAD del logging, no el formato.

El formato puede cambiar cuando quieras. Lo que no puede cambiar es que el
contenido de la conversacion de un usuario no salga en el nivel por defecto:
los logs del contenedor los lee cualquiera con acceso al panel de despliegue.

Se captura con un handler propio en vez de mirar stdout, asi el test no depende
de como se imprime.
"""

import logging

from core.logging_config import LIBRERIAS_RUIDOSAS, configurar_logging
from core.settings import Settings

MENSAJE_DEL_USUARIO = "Hola, soy Ana Lopez, mi telefono es 5512345678"


class Capturador(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)

    def texto(self) -> str:
        return "\n".join(r.getMessage() for r in self.records)


def capturar(level: str, emitir) -> str:
    configurar_logging(level)
    cap = Capturador()
    root = logging.getLogger()
    root.addHandler(cap)
    try:
        emitir(logging.getLogger("app.channels.kommo"))
    finally:
        root.removeHandler(cap)
    return cap.texto()


# --- En INFO (el default) el contenido de la conversacion NO sale ---
salida = capturar("INFO", lambda log: log.debug("AI RESPONSE: %s", MENSAJE_DEL_USUARIO))
assert MENSAJE_DEL_USUARIO not in salida, "el mensaje del usuario se filtro en INFO"

# --- ...pero el marcador de etapa SI, para poder diagnosticar en produccion ---
salida = capturar("INFO", lambda log: log.info("AI RESPONSE generada (%s caracteres)", 42))
assert "AI RESPONSE generada" in salida
assert "42" in salida

# --- Los errores siguen visibles en INFO: son los que se necesitan ---
salida = capturar("INFO", lambda log: log.error("KOMMO LEAD ERROR: %s", "timeout"))
assert "KOMMO LEAD ERROR" in salida

# --- En DEBUG el contenido SI sale: sin eso no se puede depurar ---
salida = capturar("DEBUG", lambda log: log.debug("AI RESPONSE: %s", MENSAJE_DEL_USUARIO))
assert MENSAJE_DEL_USUARIO in salida

# --- El default de LOG_LEVEL es INFO. Si alguien lo deja en DEBUG, el fix
#     de privacidad se pierde entero sin que nadie se entere. ---
assert Settings(_env_file=None).log_level.upper() == "INFO"

# --- Un nivel invalido cae a INFO, no deja el proceso sin logging ---
salida = capturar("BASURA", lambda log: log.info("sigue logueando"))
assert "sigue logueando" in salida
salida = capturar("BASURA", lambda log: log.debug("esto no"))
assert "esto no" not in salida

# --- httpx y compania quedan en WARNING: en INFO loguean una linea por
#     request con la URL completa, y esas URLs llevan el lead_id. ---
configurar_logging("INFO")
for nombre in LIBRERIAS_RUIDOSAS:
    assert logging.getLogger(nombre).level == logging.WARNING, nombre

cap = Capturador()
logging.getLogger().addHandler(cap)
try:
    logging.getLogger("httpx").info(
        "HTTP Request: POST https://x.kommo.com/api/v4/leads/12345678"
    )
    logging.getLogger("httpx").warning("timeout real")
finally:
    logging.getLogger().removeHandler(cap)
assert "12345678" not in cap.texto(), "la URL con lead_id se filtro en INFO"
assert "timeout real" in cap.texto(), "httpx dejo de avisar errores reales"

# --- El proveedor del LLM tampoco filtra. Ojo: la jerarquia de loggers va
#     por PUNTO, asi que "google" no cubre "google_genai"; son dos raices
#     distintas y hay que nombrar las dos. ---
configurar_logging("INFO")
cap = Capturador()
logging.getLogger().addHandler(cap)
try:
    logging.getLogger("google_genai.models").info("request: %s", MENSAJE_DEL_USUARIO)
    logging.getLogger("langchain_google_genai.chat_models").info(
        "prompt: %s", MENSAJE_DEL_USUARIO
    )
    logging.getLogger("openai._base_client").info("request: %s", MENSAJE_DEL_USUARIO)
    logging.getLogger("langchain_openai.chat_models").info("%s", MENSAJE_DEL_USUARIO)
    logging.getLogger("langchain_anthropic.chat_models").info("%s", MENSAJE_DEL_USUARIO)
    logging.getLogger("langchain_core.callbacks").info("%s", MENSAJE_DEL_USUARIO)
    logging.getLogger("langsmith.client").info("run inputs: %s", MENSAJE_DEL_USUARIO)
finally:
    logging.getLogger().removeHandler(cap)
assert MENSAJE_DEL_USUARIO not in cap.texto(), (
    "el proveedor del LLM filtro la conversacion en INFO"
)

# --- Todo proveedor que soporta core/llm.py queda cubierto, no solo el
#     activo: el fork cambia de proveedor por .env sin tocar codigo. ---
configurar_logging("INFO")
for raiz in ("google", "google_genai", "openai", "anthropic",
             "langchain_google_genai", "langchain_openai", "langchain_anthropic",
             "langchain_core", "langsmith"):
    nivel = logging.getLogger(raiz).getEffectiveLevel()
    assert nivel >= logging.WARNING, f"{raiz} quedo abierto en INFO"

# --- Idempotente: dos llamadas no duplican cada linea ---
configurar_logging("INFO")
configurar_logging("INFO")
assert len(logging.getLogger().handlers) == 1

print("test_logging_config OK")
