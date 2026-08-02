# Imagen de despliegue del bot (FastAPI + uvicorn).
# Dokploy construye esta imagen desde el repo en cada push.
FROM python:3.12-slim

# - PYTHONUNBUFFERED: logs salen de inmediato (no se quedan en buffer)
# - PYTHONDONTWRITEBYTECODE: no ensucia el contenedor con .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instalar dependencias primero para aprovechar el cache de capas:
# si no cambia requirements.txt, Docker reusa esta capa.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto del codigo (lo excluido va en .dockerignore).
COPY . .

# Correr como usuario no-root.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Al arrancar: crear/actualizar tablas y luego servir.
# - setup_postgres_memory.py: tablas del checkpointer (historial de conversacion)
# - setup_app_db.py: tablas propias (perfiles y metricas)
# UN solo worker a proposito: locks de sesion, dedup y pending_ai_responses
# viven en memoria del proceso. Dos workers = respuestas dobles.
CMD ["sh", "-c", "python scripts/setup_postgres_memory.py && python scripts/setup_app_db.py && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"]
