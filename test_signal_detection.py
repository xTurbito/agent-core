"""Pruebas de la deteccion de senales por regex (pura, sin LLM ni BD).

Congela los patrones base: si un cambio de regex deja de detectar
"cuanto cuesta" como asked_price, esto lo cacha antes que un cliente.
"""

from app.business.signal_detection import detect_text_signals, merge_signal_patterns

# --- Deteccion base ---

assert "asked_price" in detect_text_signals("Hola, cuanto cuesta la limpieza?")
assert "asked_price" in detect_text_signals("y el PRECIO?")  # case-insensitive via .lower()
print("OK: asked_price")

assert "asked_availability" in detect_text_signals("tienen cita para el viernes?")
print("OK: asked_availability")

assert "requested_human" in detect_text_signals("quiero hablar con un asesor")
assert "requested_human" in detect_text_signals("me puede atender un humano?")
print("OK: requested_human")

assert "clear_purchase_intent" in detect_text_signals("me interesa, quiero agendar")
print("OK: clear_purchase_intent")

assert "provided_preferred_date" in detect_text_signals("puede ser el 10/06?")
assert "provided_preferred_date" in detect_text_signals("el viernes si puedo")
print("OK: provided_preferred_date")

# Un texto puede disparar varias senales a la vez
varias = detect_text_signals("cuanto cuesta y hay lugar manana?")
assert "asked_price" in varias
assert "asked_availability" in varias
print("OK: multiples senales en un texto")

# Texto neutro no dispara nada
assert detect_text_signals("hola buenas tardes") == []
print("OK: saludo no dispara senales")

# --- Patrones custom ---

custom = {"pregunta_por_bici": [r"\bbici\b", r"\bbicicleta\b"]}

con_custom = detect_text_signals("me interesa una bici electrica", custom_patterns=custom)
assert "pregunta_por_bici" in con_custom
assert "clear_purchase_intent" in con_custom  # los base siguen activos
print("OK: patrones custom se suman a los base")

# merge extiende una senal existente sin borrar sus patrones originales
merged = merge_signal_patterns({"asked_price": [r"\bcuanto sale\b"]})
assert r"\bprecio\b" in merged["asked_price"]
assert r"\bcuanto sale\b" in merged["asked_price"]
print("OK: merge extiende sin pisar patrones base")

# merge sin custom regresa copia (mutarla no afecta la base)
copia = merge_signal_patterns()
copia["asked_price"].append("MUTADO")
assert "MUTADO" not in merge_signal_patterns()["asked_price"]
print("OK: merge regresa copia, no la referencia base")

print("\nTodas las pruebas de deteccion de senales pasaron.")
