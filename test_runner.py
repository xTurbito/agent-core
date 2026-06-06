from dotenv import load_dotenv
load_dotenv()

from core.llm import make_llm
from core.agent import build_agent
from core.memory import make_checkpointer
from core.runner import AgentRunner

agent = build_agent(
    make_llm(),
    [],
    "Eres un asistente amable. Responde en espanol, breve.",
    checkpointer=make_checkpointer(),
)

runner = AgentRunner(agent)   # creas el runner una vez

# ahora usar el bot es UNA linea, sin plomeria
print(runner.responder("cliente-123", "Hola, me llamo Miguel."))
print(runner.responder("cliente-123", "Como me llamo?"))
