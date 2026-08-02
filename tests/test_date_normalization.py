"""Pruebas de normalizacion deterministica de fechas relativas."""

from datetime import date

from app.business.date_normalization import normalize_client_date

TODAY = date(2026, 7, 5)  # domingo


manana = normalize_client_date("mañana puedo", today=TODAY)
assert manana is not None
assert manana.status == "confirmed"
assert manana.date == "2026-07-06"
print("OK: mañana -> fecha confirmada")

pasado = normalize_client_date("pasado mañana en la tarde", today=TODAY)
assert pasado is not None
assert pasado.date == "2026-07-07"
print("OK: pasado mañana -> fecha confirmada")

viernes = normalize_client_date("el viernes si puedo", today=TODAY)
assert viernes is not None
assert viernes.status == "confirmed"
assert viernes.date == "2026-07-10"
print("OK: dia de semana simple -> siguiente ocurrencia")

sabado_que_viene = normalize_client_date("el sábado que viene", today=TODAY)
assert sabado_que_viene is not None
assert sabado_que_viene.status == "confirmed"
assert sabado_que_viene.date == "2026-07-11"
assert sabado_que_viene.needs_confirmation is False
print("OK: dia con 'que viene' -> fecha confirmada")

proximo_martes = normalize_client_date("el próximo martes", today=TODAY)
assert proximo_martes is not None
assert proximo_martes.status == "confirmed"
assert proximo_martes.date == "2026-07-07"
print("OK: dia con 'proximo' -> fecha confirmada")

ambiguo = normalize_client_date("el que viene me queda bien", today=TODAY)
assert ambiguo is not None
assert ambiguo.status == "ambiguous"
assert ambiguo.date is None
print("OK: 'el que viene' sin dia -> ambiguo")

explicita = normalize_client_date("puedo el 10/07", today=TODAY)
assert explicita is not None
assert explicita.status == "confirmed"
assert explicita.date == "2026-07-10"
print("OK: fecha numerica -> confirmada")

mes_nombre = normalize_client_date("puedo el 12 de julio", today=TODAY)
assert mes_nombre is not None
assert mes_nombre.date == "2026-07-12"
print("OK: fecha con mes escrito -> confirmada")

solo_horario = normalize_client_date("en la mañana", today=TODAY)
assert solo_horario is None
print("OK: 'en la mañana' no se confunde con mañana fecha")

manana_en_manana = normalize_client_date("mañana en la mañana", today=TODAY)
assert manana_en_manana is not None
assert manana_en_manana.date == "2026-07-06"
print("OK: 'mañana en la mañana' conserva mañana como fecha")

print("\nTodas las pruebas de normalizacion de fechas pasaron.")
