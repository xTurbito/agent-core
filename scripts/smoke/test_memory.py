from dotenv import load_dotenv
load_dotenv()

from core.llm import make_llm
from core.agent import build_agent
from core.memory import make_checkpointer

agent = build_agent(
    make_llm(),
    [],
    "Eres un asistente amable. Responde en espanol, breve.",
    checkpointer=make_checkpointer(),
)


# El thread_id identifica la conversacion. En WhatsApp seria el numero del cliente.
config = {"configurable": {"thread_id": "cliente-123"}}

# Primer mensaje
r1 = agent.invoke({"messages": [("user", "Hola, me llamo Miguel.")]}, config)
print("Bot:", r1["messages"][-1].content)

# Segundo mensaje, MISMO thread_id
r2 = agent.invoke({"messages": [("user", "Como me llamo?")]}, config)
print("Bot:", r2["messages"][-1].content)