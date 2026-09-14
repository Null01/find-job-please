FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Imagen slim por defecto (solo dependencias base → ranker "keyword").
# Para incluir el ranker semántico (torch + sentence-transformers, ~1.5 GB):
#   docker build --build-arg INSTALL_EMBEDDINGS=true ...
# docker-compose lo activa en local; Render usa el default (false) = imagen liviana.
ARG INSTALL_EMBEDDINGS=false

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_EMBEDDINGS" = "true" ]; then \
        pip install --no-cache-dir -r requirements-embeddings.txt; \
    fi

COPY . .

# Genera los estáticos con el storage de prod (WhiteNoise + manifiesto).
# La clave dummy es solo para este paso de build; no se usa en runtime.
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY="build-only-dummy-key-not-used-at-runtime" \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Arranque de producción. Render inyecta $PORT; en local, docker-compose
# sobreescribe este CMD con runserver.
# Arranque de producción:
#  1) migrate — el plan free de Render no soporta preDeployCommand, así que las
#     migraciones se aplican aquí (idempotente: no-op si ya están aplicadas).
#  2) gunicorn — workers=1 por defecto (cabe en free, 512 MB); subir con
#     WEB_CONCURRENCY en planes con más RAM. El sync corre en un hilo aparte.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
