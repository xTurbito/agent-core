"""Guardianes estructurales: el prompt pide, esto obliga.

Un system prompt es probabilistico. Por mas explicita que sea la regla ("nunca
digas que la cita quedo agendada sin llamar la tool"), el modelo la rompe: en
pruebas reales afirmo citas inexistentes y horarios que nunca consulto. Cuando
el agente afirma como hecho consumado algo que solo una tool puede saber, la
mentira llega al chat y el usuario actua sobre ella.

Un guardian no depende de que el LLM obedezca: lee el borrador ANTES de que
salga, y si afirma el hecho sin que la tool que lo respalda haya respondido en
ESTE turno, reintenta la generacion con una correccion inyectada.
"""

from collections.abc import Callable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from core.runner import extract_text

ClaimDetector = Callable[[str], bool]


class ToolClaimGuardMiddleware(AgentMiddleware):
    """Reintenta cuando la respuesta afirma un hecho que ninguna tool respaldo.

    Parametros:
      claim_detector: recibe el texto final y dice si AFIRMA el hecho. Debe
        distinguir afirmacion de invitacion o intencion ("tu cita quedo
        agendada" si, "te gustaria agendar?" no); de lo contrario el guardian
        reintenta de mas y encarece cada turno.
      tool_name: la tool que es la unica fuente valida de ese hecho.
      success_marker: subcadena que debe aparecer en el resultado de la tool
        para contar como respaldo. Un resultado de error o vacio no respalda
        nada, por eso no basta con que la tool haya sido llamada.
      nudge: correccion que se agrega al system prompt en el reintento.
    """

    def __init__(
        self,
        *,
        claim_detector: ClaimDetector,
        tool_name: str,
        success_marker: str,
        nudge: str,
    ):
        super().__init__()
        self._claim_detector = claim_detector
        self._tool_name = tool_name
        self._success_marker = success_marker
        self._nudge = nudge

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        response = handler(request)

        mensaje = response.result[-1] if response.result else None
        if mensaje is None or getattr(mensaje, "tool_calls", None):
            return response  # va a ejecutar tools; aun no es respuesta final

        texto = extract_text(mensaje.content)
        if not self._claim_detector(texto):
            return response
        if self._respaldada_en_turno(list(request.messages)):
            return response

        base = request.system_message.content if request.system_message else ""
        request.system_message = SystemMessage(content=f"{base}{self._nudge}")
        return handler(request)

    def _respaldada_en_turno(self, messages: list) -> bool:
        """Busca el respaldo hacia atras SOLO dentro del turno actual.

        Se corta en el ultimo mensaje del usuario a proposito: una consulta
        exitosa de hace tres turnos no respalda lo que el agente afirma hoy
        (la disponibilidad de ayer no es la de ahora).
        """
        for mensaje in reversed(messages):
            if isinstance(mensaje, HumanMessage):
                return False
            if (
                isinstance(mensaje, ToolMessage)
                and mensaje.name == self._tool_name
                and self._success_marker in str(mensaje.content)
            ):
                return True
        return False
