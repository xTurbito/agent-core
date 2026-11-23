"""Configuracion de logging del proceso.

Generico: no sabe de ningun canal ni negocio. Las trazas con datos de la persona
que escribe van a DEBUG (apagado por defecto); los errores se quedan visibles, y
los parametros sensibles de URL (?secret=) se ocultan en todas las lineas.
"""

import logging
import re
import sys
from typing import Any
from urllib.parse import unquote

DEFAULT_LEVEL = "INFO"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Estas librerias loguean UNA LINEA POR REQUEST en INFO, con la URL completa.
# Las URLs de los servicios que consumimos llevan identificadores (lead, cita,
# contacto), asi que a INFO filtran datos aunque el resto del logging este
# limpio. A WARNING siguen avisando cuando algo falla de verdad.
# Ojo: son nombres de logger TOP-LEVEL, y la jerarquia va por punto. "google"
# NO cubre "google_genai": son dos raices distintas, hay que nombrar las dos.
LIBRERIAS_RUIDOSAS = (
    "httpx",
    "httpcore",
    "urllib3",
    "google",
    "google_genai",
    "openai",
    "anthropic",
    # Los wrappers de langchain estan en el camino caliente igual que el SDK
    # de abajo. Van TODOS los proveedores que soporta core/llm.py, no solo el
    # activo: el fork cambia de proveedor por .env sin tocar codigo, asi que
    # listar solo el de hoy reabre la fuga cuando alguien cambia LLM_PROVIDER.
    "langchain_core",
    "langchain_google_genai",
    "langchain_openai",
    "langchain_anthropic",
    # Si alguien prende LANGCHAIN_TRACING_V2, este logger lleva el contenido
    # completo de cada corrida.
    "langsmith",
)


# Parametros de URL cuyo valor no debe salir en ningun log ni evento de error.
# El webhook de Kommo no firma y el secreto viaja en la URL (?secret=...), asi que
# uvicorn lo escribe en cada linea del access log. El fork puede pasar otros.
PARAMETROS_URL_SENSIBLES = ("secret",)

OCULTO = "***"


# Un par nombre=valor. El nombre puede traer %XX (Starlette lo decodifica antes de
# autenticar: "se%63ret" llega como "secret"), asi que se compara DECODIFICADO. El
# lookbehind obliga a que el nombre empiece donde empieza una palabra, y eso mantiene
# la busqueda lineal (sin backtracking).
_PAR = re.compile(r"(?<![\w%.-])([\w%.-]+)=([^&\s\"']+)")


def ocultar_parametros(texto: str, parametros: tuple[str, ...] = PARAMETROS_URL_SENSIBLES) -> str:
    """Reemplaza el valor de los parametros sensibles por "***"; el resto queda igual."""
    if not parametros:
        return texto
    sensibles = {p.lower() for p in parametros}

    def _reemplazo(par: re.Match[str]) -> str:
        if unquote(par.group(1)).lower() in sensibles:
            return f"{par.group(1)}={OCULTO}"
        return par.group(0)

    return _PAR.sub(_reemplazo, texto)


class OcultarParametrosFilter(logging.Filter):
    """Oculta los parametros sensibles de un LogRecord.

    Redacta el mensaje y CADA argumento por separado, sin juntarlos: el
    AccessFormatter de uvicorn desarma record.args en 5 campos (cliente, metodo,
    ruta, version, status) y se rompe si cambia su cantidad o su tipo.
    """

    def __init__(self, parametros: tuple[str, ...] = PARAMETROS_URL_SENSIBLES):
        super().__init__()
        self._parametros = tuple(parametros)

    def _ocultar(self, valor: Any) -> Any:
        return ocultar_parametros(valor, self._parametros) if isinstance(valor, str) else valor

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.args:
            record.msg = self._ocultar(record.msg)
        # Con argumentos NO se toca la plantilla: en "secret=%s" el regex tomaria
        # el "%s" como valor y se romperia el formateo. Se redacta cada argumento.
        elif isinstance(record.args, tuple):
            record.args = tuple(self._ocultar(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: self._ocultar(v) for k, v in record.args.items()}
        return True


class OcultarParametrosFormatter(logging.Formatter):
    """Formatter que oculta los parametros sensibles de la linea YA formateada.

    Cubre lo que el filtro por argumento no ve: la plantilla trae el nombre
    ("?secret=%s") y el valor llega aparte, o el secreto va dentro de un traceback.
    Si recibe un `original`, le delega primero el formato (uvicorn tiene formatters
    propios, como el AccessFormatter, que necesitan record.args intactos) y limpia
    solo el texto final.
    """

    def __init__(
        self,
        fmt: str | None = None,
        parametros: tuple[str, ...] = PARAMETROS_URL_SENSIBLES,
        original: logging.Formatter | None = None,
    ):
        super().__init__(fmt)
        self._parametros = tuple(parametros)
        self.original = original

    def format(self, record: logging.LogRecord) -> str:
        texto = self.original.format(record) if self.original else super().format(record)
        return ocultar_parametros(texto, self._parametros)


# uvicorn escribe el access log aqui, y estos loggers NO propagan al root.
LOGGERS_DE_UVICORN = ("uvicorn", "uvicorn.access", "uvicorn.error")


def _poner_filtro(objetivo: logging.Logger | logging.Handler, filtro: logging.Filter) -> None:
    for existente in [f for f in objetivo.filters if isinstance(f, OcultarParametrosFilter)]:
        objetivo.removeFilter(existente)  # idempotente: no se acumula al recargar
    objetivo.addFilter(filtro)


def _envolver_formatter(handler: logging.Handler, parametros: tuple[str, ...]) -> None:
    """Pone la redaccion de la linea final sobre el formatter que ya tenia el handler."""
    actual = handler.formatter
    if isinstance(actual, OcultarParametrosFormatter):
        actual = actual.original  # idempotente: no se envuelve dos veces
    handler.setFormatter(OcultarParametrosFormatter(parametros=parametros, original=actual))


def configurar_logging(
    level: str | None = None,
    parametros_url_sensibles: tuple[str, ...] = PARAMETROS_URL_SENSIBLES,
) -> None:
    """Deja el root logger listo. Idempotente: llamarlo dos veces no duplica.

    El nivel entra por parametro (lo lee el settings del fork desde .env) para
    que este modulo no dependa de ninguna config concreta.
    """
    # Un typo en el .env no debe dejar el proceso sin logging: cae a INFO.
    crudo = (level or DEFAULT_LEVEL).upper()
    nivel = getattr(logging, crudo, None)
    if not isinstance(nivel, int):
        nivel = logging.INFO

    root = logging.getLogger()
    root.setLevel(nivel)

    # Sin esto, un reload de uvicorn agrega un handler nuevo cada vez y cada
    # linea sale repetida tantas veces como se haya recargado el modulo.
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    filtro = OcultarParametrosFilter(parametros_url_sensibles)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(OcultarParametrosFormatter(FORMAT, parametros_url_sensibles))
    _poner_filtro(handler, filtro)
    root.addHandler(handler)

    # uvicorn configura su logging ANTES de importar la app: sus loggers y
    # handlers ya existen aqui, y el access log es donde queda la URL completa.
    for nombre in LOGGERS_DE_UVICORN:
        logger_uvicorn = logging.getLogger(nombre)
        _poner_filtro(logger_uvicorn, filtro)
        for h in logger_uvicorn.handlers:
            _poner_filtro(h, filtro)
            _envolver_formatter(h, parametros_url_sensibles)

    for nombre in LIBRERIAS_RUIDOSAS:
        logging.getLogger(nombre).setLevel(logging.WARNING)
