"""Tool: consultar disponibilidad.

Por ahora datos simulados (inventados a mano).
Despues la conectamos a la API real del cliente.
"""

from langchain_core.tools import tool

@tool 
def consultar_disponibilidad(fecha: str) -> str:
    """Consulta los horarios disponibles para una fecha.

        Usar cuando el cliente pregunte por disponibilidad, cupos u horarios
     Args:
        fecha: Fecha en formato AAAA-MM-DD, por ejemplo "2026-06-10".
    """
    # TODO: reemplazar por llamada real a la API del cliente
    cupos = {
        "2026-06-10": ["09:00", "11:30", "16:00"],
        "2026-06-11": ["10:00", "15:00"],
    }

    horarios = cupos.get(fecha)
    if not horarios:
        return f"No hay disponibilidad para {fecha}."
    return f"Horarios para {fecha}: {', '.join(horarios)}."

