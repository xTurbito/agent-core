"""Modelo de respaldo ante una respuesta vacia, cortada o con error del primario.

Un modelo que razona sin tope puede gastar todo max_tokens y no dejar texto;
insistirle al mismo modelo repite el problema. Contrato:
1. reasoning_effort llega a los proveedores que lo aceptan.
2. Ante vacio, cortada o error, esa llamada se repite UNA vez con el respaldo.
3. Un respaldo a medias falla al arrancar, no a mitad de un turno.
Sin red real.
"""

from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, SystemMessage

from core.agent import EmptyResponseRetryMiddleware
from core.llm import make_llm
from core.settings import Settings

# --- 1. reasoning_effort llega a los proveedores que lo aceptan ---

llm = make_llm("openrouter", "deepseek/deepseek-v4.1-flash", api_key="k", reasoning_effort="none")
assert llm.reasoning_effort == "none"
llm = make_llm("openai", "gpt-6-luna", api_key="k", reasoning_effort="none")
assert llm.reasoning_effort == "none"
print("OK: reasoning_effort llega a openrouter y a openai")

llm = make_llm("openrouter", "deepseek/deepseek-v4.1-flash", api_key="k")
assert llm.reasoning_effort is None
print("OK: sin reasoning_effort configurado no se manda nada (comportamiento previo)")

# --- 2. el modelo de respaldo contesta la llamada que el primario no pudo ---

PRIMARIO = "modelo-primario"
RESPALDO = "modelo-de-respaldo"


class FakeRequest:
    def __init__(self, model=PRIMARIO):
        self.model = model
        self.system_message = SystemMessage(content="prompt base")

    def override(self, **cambios):
        return FakeRequest(model=cambios.get("model", self.model))


def respuesta(texto: str = "", finish_reason: str = "stop") -> ModelResponse:
    return ModelResponse(
        result=[AIMessage(content=texto, response_metadata={"finish_reason": finish_reason})]
    )


def correr(primario, respaldo_responde=None, con_respaldo=True):
    """Devuelve (respuesta, modelos llamados en orden)."""
    llamados: list[str] = []

    def handler(request):
        llamados.append(request.model)
        if request.model == PRIMARIO:
            if isinstance(primario, Exception):
                raise primario
            return primario
        if isinstance(respaldo_responde, Exception):
            raise respaldo_responde
        return respaldo_responde

    middleware = EmptyResponseRetryMiddleware(respaldo=RESPALDO if con_respaldo else None)
    return middleware.wrap_model_call(FakeRequest(), handler), llamados


resultado, llamados = correr(respuesta("hola"), respuesta("no deberia usarse"))
assert resultado.result[-1].content == "hola"
assert llamados == [PRIMARIO]
print("OK: si el primario responde bien, el respaldo no se toca")

resultado, llamados = correr(respuesta(""), respuesta("respuesta del respaldo"))
assert resultado.result[-1].content == "respuesta del respaldo"
assert llamados == [PRIMARIO, RESPALDO]
print("OK: respuesta vacia -> una sola llamada al respaldo, sin insistirle al primario")

resultado, llamados = correr(
    respuesta("¡Qué bueno que quieras agendar", finish_reason="length"),
    respuesta("respuesta completa"),
)
assert resultado.result[-1].content == "respuesta completa"
assert llamados == [PRIMARIO, RESPALDO]
print("OK: respuesta cortada por limite de tokens -> respaldo")

resultado, llamados = correr(TimeoutError("proveedor colgado"), respuesta("sigo aqui"))
assert resultado.result[-1].content == "sigo aqui"
assert llamados == [PRIMARIO, RESPALDO]
print("OK: el primario truena o se cuelga -> respaldo")

resultado, llamados = correr(respuesta(""), respuesta(""))
assert resultado.result[-1].content == ""
assert llamados == [PRIMARIO, RESPALDO]
print("OK: si el respaldo tambien sale vacio no se sigue reintentando")

try:
    correr(respuesta(""), RuntimeError("respaldo caido"))
except RuntimeError as exc:
    assert "respaldo caido" in str(exc)
else:
    raise AssertionError("el fallo del respaldo debe subir para que el canal lo trate")
print("OK: si el respaldo truena, el error sube al canal")

try:
    correr(TimeoutError("proveedor colgado"), con_respaldo=False)
except TimeoutError:
    pass
else:
    raise AssertionError("sin respaldo, el error del primario debe subir igual que antes")
print("OK: sin respaldo configurado, un error del primario sube igual que antes")

# --- la configuracion del respaldo se valida al arrancar ---

sin_respaldo = Settings(_env_file=None)
assert sin_respaldo.require_fallback_llm_api_key() is None
print("OK: sin LLM_FALLBACK_PROVIDER no hay respaldo ni nada que validar")

completo = Settings(
    _env_file=None,
    llm_fallback_provider="openai",
    llm_fallback_model="gpt-6-luna",
    llm_fallback_reasoning_effort="none",
    openai_api_key="k",
)
assert completo.require_fallback_llm_api_key() == "k"
print("OK: respaldo completo devuelve su key")

for incompleto, falta in (
    ({"llm_fallback_provider": "openai", "llm_fallback_model": "gpt-6-luna"}, "OPENAI_API_KEY"),
    ({"llm_fallback_provider": "openai", "openai_api_key": "k"}, "LLM_FALLBACK_MODEL"),
    ({"llm_fallback_provider": "inventado", "llm_fallback_model": "x"}, "LLM_FALLBACK_PROVIDER"),
):
    try:
        Settings(_env_file=None, **incompleto).require_fallback_llm_api_key()
    except RuntimeError as exc:
        assert falta in str(exc), (falta, str(exc))
    else:
        raise AssertionError(f"un respaldo sin {falta} debe fallar al arrancar")
print("OK: un respaldo a medias falla al arrancar, no a mitad de un turno")

print("\nTodas las pruebas del modelo de respaldo pasaron.")
