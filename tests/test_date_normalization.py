"""Pruebas de normalizacion deterministica de fechas relativas."""

from datetime import date

from core.date_normalization import months_between, normalize_client_date

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

# Bug real: "del" en vez de "de" antes
# del año no matcheaba el regex del año, asi que el año explicito se
# perdia y la fecha se empujaba un año al futuro (2027 en vez de 2025).
con_del = normalize_client_date("6 de mayo del 2025", today=TODAY)
assert con_del is not None
assert con_del.date == "2025-05-06", con_del.date
print("OK: 'del <año>' conserva el año explicito, no lo empuja al futuro")

rango = normalize_client_date("5 de mayo del 10 al 12", today=date(2026, 4, 1))
assert rango is not None and rango.date == "2026-05-05", rango
print("OK: 'del 10 al 12' es un rango de dias, no el año 2010")

# Bug real: el cliente dijo "lunes 17 de
# noviembre" y "miercoles 19 de noviembre", BEA repitio esos nombres sin
# verificar -- ninguno de los dos es correcto (son martes y jueves). El
# nombre que dice el cliente se IGNORA; weekday_name siempre es el real.
con_dia_equivocado = normalize_client_date("el lunes 17 de noviembre de 2026", today=TODAY)
assert con_dia_equivocado is not None
assert con_dia_equivocado.date == "2026-11-17"
assert con_dia_equivocado.weekday_name == "martes", con_dia_equivocado.weekday_name
print("OK: weekday_name es el dia real, no el que dijo el cliente")

otro_dia_equivocado = normalize_client_date("el miercoles 19 de noviembre de 2026", today=TODAY)
assert otro_dia_equivocado is not None
assert otro_dia_equivocado.weekday_name == "jueves", otro_dia_equivocado.weekday_name
print("OK: segundo caso del mismo bug tambien calcula el dia real")

# Sin fecha confirmada, no hay weekday_name que calcular.
assert normalize_client_date("en la mañana", today=TODAY) is None

solo_horario = normalize_client_date("en la mañana", today=TODAY)
assert solo_horario is None
print("OK: 'en la mañana' no se confunde con mañana fecha")

manana_en_manana = normalize_client_date("mañana en la mañana", today=TODAY)
assert manana_en_manana is not None
assert manana_en_manana.date == "2026-07-06"
print("OK: 'mañana en la mañana' conserva mañana como fecha")

# months_between: meses de calendario completos, no dias/30. Caso real
# 6 de mayo 2025 -> 4 de noviembre 2026 son 17 meses
# completos (el aniversario de 18 meses cae el 6 de noviembre, 2 dias
# despues de "hoy"), no 18.
assert months_between(date(2025, 5, 6), date(2026, 11, 4)) == 17
assert months_between(date(2025, 5, 6), date(2026, 11, 6)) == 18
assert months_between(date(2026, 1, 1), date(2026, 1, 1)) == 0
assert months_between(date(2026, 1, 1), date(2025, 1, 1)) == -12
print("OK: months_between cuenta meses de calendario completos")

# Bug de auditoria: start.day en 29/30/31 y el mes destino es
# mas corto -- el aniversario clampeado debe contar el mes como completo,
# no restarlo. Un 31 de enero a un 30 de junio son 17 meses (el
# aniversario "31 de junio" no existe, se clampa a 30), no 16.
assert months_between(date(2025, 1, 31), date(2026, 6, 30)) == 17
assert months_between(date(2025, 1, 31), date(2025, 2, 28)) == 1
print("OK: months_between clampea el aniversario al ultimo dia del mes corto")

print("\nTodas las pruebas de normalizacion de fechas pasaron.")
