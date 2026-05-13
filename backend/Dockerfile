# Dockerfile para Cloud Run
# - Imagen slim para minimizar superficie y boot time.
# - Usuario no-root para principio de menor privilegio.
# - Listen en el puerto $PORT que Cloud Run inyecta.
# - Workers=1 + worker-class uvicorn: SSE necesita conexiones long-lived,
#   los workers extra de gunicorn no aportan en este tipo de carga.

FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim

# Crear usuario no-root
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Instalar wheels pre-construidos
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copiar código
COPY --chown=app:app . .

USER app

# Cloud Run inyecta PORT (default 8080)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Exponer puerto (informativo, Cloud Run no lo usa)
EXPOSE 8080

# IMPORTANTE: usar exec form para que las señales lleguen al uvicorn
CMD exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers 1 \
    --timeout-keep-alive 75 \
    --proxy-headers \
    --forwarded-allow-ips='*'
