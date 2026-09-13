FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Torch CPU-only primero (evita bajar las libs de CUDA, imagen mucho más liviana).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Genera los estáticos con el storage de prod (WhiteNoise + manifiesto).
# La clave dummy es solo para este paso de build; no se usa en runtime.
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY="build-only-dummy-key-not-used-at-runtime" \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Arranque de producción. Render inyecta $PORT; en local, docker-compose
# sobreescribe este CMD con runserver.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2"]
