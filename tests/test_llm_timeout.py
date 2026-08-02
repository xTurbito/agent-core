"""Pruebas de que make_llm siempre manda un timeout al proveedor.

Sin timeout, una llamada colgada al proveedor deja el lock por-sesion de
AgentRunner tomado para siempre (visto en pruebas de carga real). Sin red:
mockea el constructor de cada proveedor."""

from unittest.mock import patch

from core.llm import DEFAULT_TIMEOUT_SECONDS, make_llm

with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_google:
    make_llm("google", "gemini-3.1-flash-lite", api_key="fake")
    _, kwargs = mock_google.call_args
    assert kwargs["timeout"] == DEFAULT_TIMEOUT_SECONDS
    print("OK: google recibe el timeout por default")

with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_google:
    make_llm("google", "gemini-3.1-flash-lite", api_key="fake", timeout=5)
    _, kwargs = mock_google.call_args
    assert kwargs["timeout"] == 5
    print("OK: un timeout explicito no se pisa con el default")

with patch("langchain_anthropic.ChatAnthropic") as mock_anthropic:
    make_llm("anthropic", "claude-fake", api_key="fake")
    _, kwargs = mock_anthropic.call_args
    assert kwargs["timeout"] == DEFAULT_TIMEOUT_SECONDS
    print("OK: anthropic recibe el timeout por default")

with patch("langchain_openai.ChatOpenAI") as mock_openai:
    make_llm("openai", "gpt-fake", api_key="fake")
    _, kwargs = mock_openai.call_args
    assert kwargs["timeout"] == DEFAULT_TIMEOUT_SECONDS
    print("OK: openai recibe el timeout por default")

print("\nTodas las pruebas de timeout del LLM pasaron.")
