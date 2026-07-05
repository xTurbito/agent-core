"""Pruebas de la logica de calificacion y handoff (pura, sin LLM ni BD).

Congela el criterio comercial: pesos de senales, umbrales de score y
politicas de escalamiento. Si cambias SIGNAL_WEIGHTS o HANDOFF_POLICIES,
estos asserts te avisan que estas moviendo el negocio, no solo codigo.
"""

from app.business.qualification import calculate_qualification, should_handoff

# --- Scoring ---

sin_senales = calculate_qualification([])
assert sin_senales["qualification_score"] == 0
assert sin_senales["qualification_label"] == "unknown"
assert sin_senales["qualification_reason"] is None
print("OK: sin senales -> score 0, unknown")

frio = calculate_qualification(["asked_price"])
assert frio["qualification_score"] == 10
assert frio["qualification_label"] == "cold"
print("OK: solo precio -> cold")

tibio = calculate_qualification(["asked_price", "asked_availability", "clear_purchase_intent"])
assert tibio["qualification_score"] == 55
assert tibio["qualification_label"] == "warm"
print("OK: precio+disponibilidad+intencion -> warm 55")

caliente = calculate_qualification(["booking_confirmed"])
assert caliente["qualification_score"] == 100
assert caliente["qualification_label"] == "hot"
print("OK: booking confirmado -> hot 100")

# El score se topa en 100 aunque las senales sumen mas
topado = calculate_qualification(["booking_confirmed", "purchase_completed", "requested_human"])
assert topado["qualification_score"] == 100
print("OK: score topado en 100")

# Senales duplicadas no suman doble
duplicadas = calculate_qualification(["asked_price", "asked_price", "asked_price"])
assert duplicadas["qualification_score"] == 10
print("OK: senales duplicadas no suman doble")

# Senal desconocida no truena ni suma
desconocida = calculate_qualification(["senal_que_no_existe"])
assert desconocida["qualification_score"] == 0
print("OK: senal desconocida ignorada")

# --- Handoff ---

# requested_human fuerza escalamiento en toda politica, aun con score bajo
q = calculate_qualification(["requested_human"])
h = should_handoff(["requested_human"], q, "default")
assert h["handoff_recommended"] is True
assert "requested_human" in h["handoff_reason"]
print("OK: requested_human fuerza handoff (default)")

# score alto dispara handoff por umbral (default: 80)
q = calculate_qualification(["booking_confirmed"])
h = should_handoff(["booking_confirmed"], q, "default")
assert h["handoff_recommended"] is True
print("OK: score >= 80 dispara handoff (default)")

# score bajo sin senales forzadas NO escala
q = calculate_qualification(["asked_price"])
h = should_handoff(["asked_price"], q, "default")
assert h["handoff_recommended"] is False
assert h["handoff_reason"] is None
print("OK: cold sin senal forzada no escala")

# politica sales_agent escala por objecion fuerte aunque el score sea 0
q = calculate_qualification(["strong_objection"])
h = should_handoff(["strong_objection"], q, "sales_agent")
assert h["handoff_recommended"] is True
print("OK: strong_objection escala en sales_agent")

# ...pero esa misma senal NO escala en la politica default
h = should_handoff(["strong_objection"], q, "default")
assert h["handoff_recommended"] is False
print("OK: strong_objection no escala en default")

# politica inexistente cae a default en vez de tronar
q = calculate_qualification(["requested_human"])
h = should_handoff(["requested_human"], q, "politica_inventada")
assert h["handoff_recommended"] is True
print("OK: politica desconocida cae a default")

print("\nTodas las pruebas de calificacion/handoff pasaron.")
