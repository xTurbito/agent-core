"""Casos de evals del fork: los mensajes del usuario, en orden.

Son un guion fijo: el usuario no reacciona a lo que conteste el agente, asi que
sirven para comparar corridas, no para simular a una persona. Reemplaza estos
ejemplos por conversaciones reales del negocio (las que salieron mal, sobre todo).
"""

CASOS: dict[str, list[str]] = {
    "saludo": ["Hola"],
    "disponibilidad": [
        "Hola, ¿tienen espacio el sábado?",
        "En la tarde, si se puede",
        "Perfecto, gracias",
    ],
    "fuera_de_tema": ["¿Me ayudas con mi tarea de matemáticas?"],
}
