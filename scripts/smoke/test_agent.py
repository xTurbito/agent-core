from dotenv import load_dotenv
load_dotenv()


from datetime import date
from core.llm import make_llm
from core.agent import build_agent
from app.tools.disponibilidad import consultar_disponibilidad

hoy = date.today().isoformat()   # ej. "2026-06-05"

agent = build_agent(
    make_llm(),
    [consultar_disponibilidad],
    f"Eres el asistente de una clinica dental. Responde en espanol, breve y amable. "
    f"Hoy es {hoy}. Usa esta fecha para interpretar referencias como 'manana' o '10 de junio'. "
    f"Usa las tools para datos reales. NUNCA inventes disponibilidad.",
)

result = agent.invoke({"messages": [("user", "Hay cupo el 10 de junio?")]})
print(result["messages"][-1].content)