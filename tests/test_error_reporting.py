"""Pruebas de with_error_tracking: siempre debe llamar al handler original,
y ademas reportar a un servicio externo solo cuando hay DSN configurado --
sin pegarle a la red real (se reemplaza sentry_sdk por un doble de prueba).
"""

import sys

import core.error_reporting as error_reporting


class _FakeScope:
    def __init__(self, sink: dict):
        self._sink = sink

    def set_context(self, key, value):
        self._sink[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_sentry_sdk(llamadas_init: list, llamadas_capture: list, contexto_capturado: dict):
    class _FakeSentrySdk:
        @staticmethod
        def init(**kwargs):
            llamadas_init.append(kwargs)

        @staticmethod
        def new_scope():
            return _FakeScope(contexto_capturado)

        @staticmethod
        def capture_exception(error):
            llamadas_capture.append(error)

    return _FakeSentrySdk()


llamadas_handler: list = []


def _handler_falso(error, context):
    llamadas_handler.append((error, context))


# --- Sin DSN: solo llama al handler original, nunca toca Sentry ---

error_reporting._initialized = False
llamadas_handler.clear()
init_calls: list = []
capture_calls: list = []
sys.modules["sentry_sdk"] = _fake_sentry_sdk(init_calls, capture_calls, {})

reportar = error_reporting.with_error_tracking(_handler_falso, dsn=None)
error = ValueError("boom")
reportar(error, {"source": "test"})

assert llamadas_handler == [(error, {"source": "test"})]
assert init_calls == []
assert capture_calls == []
print("OK: sin DSN, solo llama al handler original")


# --- Con DSN: llama al handler original Y reporta a Sentry, sin PII ni trazas ---

error_reporting._initialized = False
llamadas_handler.clear()
init_calls.clear()
capture_calls.clear()
contexto_capturado: dict = {}
sys.modules["sentry_sdk"] = _fake_sentry_sdk(init_calls, capture_calls, contexto_capturado)

reportar = error_reporting.with_error_tracking(_handler_falso, dsn="https://fake@dsn/1")
error2 = RuntimeError("otro boom")
reportar(error2, {"source": "test2"})

assert llamadas_handler == [(error2, {"source": "test2"})]
assert len(init_calls) == 1
assert init_calls[0]["send_default_pii"] is False
assert init_calls[0]["traces_sample_rate"] == 0.0
assert capture_calls == [error2]
assert contexto_capturado == {"app": {"source": "test2"}}
print("OK: con DSN, llama al handler original y reporta a Sentry con PII/trazas desactivadas")


# --- with_error_tracking() llamado dos veces: Sentry se inicializa UNA sola vez ---

error_reporting._initialized = False
init_calls.clear()

error_reporting.with_error_tracking(_handler_falso, dsn="https://fake@dsn/1")
error_reporting.with_error_tracking(_handler_falso, dsn="https://fake@dsn/1")

assert len(init_calls) == 1, "Sentry no debe reinicializarse si ya estaba inicializado"
print("OK: construir el reporter varias veces no reinicializa Sentry cada vez")


# --- Si el reporte a Sentry truena, el handler original igual debe correr ---


class _FakeSentrySdkRoto:
    @staticmethod
    def init(**kwargs):
        pass

    @staticmethod
    def new_scope():
        return _FakeScope({})

    @staticmethod
    def capture_exception(error):
        raise RuntimeError("Sentry esta caido")


error_reporting._initialized = False
llamadas_handler.clear()
sys.modules["sentry_sdk"] = _FakeSentrySdkRoto()

reportar = error_reporting.with_error_tracking(_handler_falso, dsn="https://fake@dsn/1")
error3 = ValueError("un error cualquiera")
reportar(error3, {})

assert llamadas_handler == [(error3, {})], "el handler original debe correr aunque Sentry falle"
print("OK: si el reporte a Sentry falla, el handler original igual corrio")


print("\nTodas las pruebas de error_reporting pasaron.")
