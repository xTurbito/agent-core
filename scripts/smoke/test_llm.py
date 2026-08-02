from dotenv import load_dotenv
load_dotenv()                      # carga GOOGLE_API_KEY del .env

from core.llm import make_llm

llm = make_llm()                   # gemini-2.5-flash por default
respuesta = llm.invoke("Dime la hora en merida y el climca.")
print(respuesta.content)
