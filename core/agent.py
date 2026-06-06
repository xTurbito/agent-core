"""Construye el agente como grafo LangGraph.

Recibe LLM + tools + prompt (+ memoria opcional), devuelve un agente listo.
El core no sabe QUE tools son; cada bot las inyecta. Eso es el desacople.
"""

from langchain.agents import create_agent

def build_agent(llm, tools, system_prompt: str, checkpointer=None):
    return create_agent(
        llm,
        tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )