"""Pruebas puras del cliente Kommo."""

from app.integrations.kommo_client import (
    MAX_EXECUTE_HANDLERS,
    adapt_text_for_kommo,
    build_continue_salesbot_body,
    build_show_handlers,
    encode_json_utf8,
    extract_contact_phone,
    split_show_text,
    strip_remaining_modern_emojis,
)

adapted = adapt_text_for_kommo("Hola 👋 que gusto verte 😊")
assert "👋" not in adapted
assert "😊" not in adapted
assert "☺" in adapted
assert adapted == "Hola que gusto verte ☺"
print("OK: emojis problematicos se adaptan para Kommo")

heart = adapt_text_for_kommo("Nos encanta atenderte 🥰")
assert heart == "Nos encanta atenderte ✨"
print("OK: emojis de cariño se cambian por simbolo seguro")

unknown_emoji = strip_remaining_modern_emojis("Hola 🫶")
assert unknown_emoji == "Hola "
print("OK: emojis modernos no mapeados se quitan")

chunks = split_show_text("x" * 81)
assert chunks == ["x" * 80, "x"]
print("OK: chunks respetan limite de 80 caracteres")

lista = adapt_text_for_kommo("Opciones:\n- Lifting  ($690)\n\n- Botox   ($250)")
assert lista == "Opciones:\n- Lifting ($690)\n- Botox ($250)"
print("OK: adapt_text_for_kommo conserva saltos de linea y colapsa lineas vacias")

chunks_lista = split_show_text("Linea uno\nLinea dos")
assert chunks_lista == ["Linea uno", "Linea dos"]
print("OK: split_show_text no junta lineas distintas en un mismo chunk")

negrita = adapt_text_for_kommo("Te gustaria el **Dyd** tradicional o **Dyd con Hilo**?")
assert negrita == "Te gustaria el *Dyd* tradicional o *Dyd con Hilo*?"
print("OK: negrita markdown (**) se convierte a asterisco simple de WhatsApp")

# Kommo rechaza con 400 "TooMany" si execute_handlers trae mas de 10 elementos.
# Una lista con una opcion por renglon quema un handler por renglon, asi que el
# limite se revienta con textos cortos (ver Miroslava / conversacion A37917).
lista_larga = "\n".join(f"- Servicio numero {index}" for index in range(1, 16))
handlers_lista = build_show_handlers(lista_larga)
assert len(handlers_lista) <= MAX_EXECUTE_HANDLERS
print("OK: una lista de 15 renglones no excede el limite de handlers de Kommo")

# En modo degradado se juntan renglones para que quepan, pero no se pierde el
# contenido mientras el texto entre en el techo real (10 bloques x 80 chars).
valores = [handler["params"]["value"] for handler in handlers_lista]
assert all(len(valor) <= 80 for valor in valores)
assert "Servicio numero 15" in " ".join(valores)
print("OK: al compactar no se pierden renglones si el texto cabe en el techo")

# Caso normal (pocos renglones): se respeta un bubble por renglon.
handlers_cortos = build_show_handlers("Linea uno\nLinea dos")
assert [handler["params"]["value"] for handler in handlers_cortos] == [
    "Linea uno",
    "Linea dos",
]
print("OK: con pocos renglones se conserva un bubble por renglon")

# Texto que ni compactado cabe: NO se recorta a proposito. Pasar de 800
# caracteres es un bug del prompt y queremos verlo, no taparlo sirviendole
# media respuesta a la clienta.
handlers_gigantes = build_show_handlers("palabra " * 400)
assert len(handlers_gigantes) > MAX_EXECUTE_HANDLERS
print("OK: un texto gigante no se recorta, revienta y se ve en el log")

body = build_continue_salesbot_body(
    "Hola ☺",
    [{"handler": "show", "params": {"type": "text", "value": "Hola ☺"}}],
)
encoded = encode_json_utf8(body)
assert "Hola ☺" in encoded.decode("utf-8")
print("OK: JSON sale como UTF-8 real")

# extract_contact_phone: forma real del payload de contactos de Kommo
contacto = {
    "id": 36697306,
    "custom_fields_values": [
        {"field_code": "EMAIL", "values": [{"value": "x@y.com"}]},
        {"field_code": "PHONE", "values": [{"value": "+5215599887766"}]},
    ],
}
assert extract_contact_phone(contacto) == "+5215599887766"
print("OK: extrae el telefono del custom field PHONE")

assert extract_contact_phone({"custom_fields_values": None}) is None
assert extract_contact_phone({}) is None
print("OK: contacto sin campos regresa None")

sin_valor = {"custom_fields_values": [{"field_code": "PHONE", "values": [{"value": "  "}]}]}
assert extract_contact_phone(sin_valor) is None
print("OK: PHONE vacio regresa None")

varios = {
    "custom_fields_values": [
        {"field_code": "PHONE", "values": [{"value": ""}, {"value": "5511122233"}]},
    ]
}
assert extract_contact_phone(varios) == "5511122233"
print("OK: brinca valores vacios y toma el primer telefono real")

print("\nTodas las pruebas del cliente Kommo pasaron.")
