# Imagen única para producer, consumer y api (cambia solo el comando).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Las dependencias se instalan antes de copiar el código para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY observatorio/ observatorio/
COPY tests/ tests/
COPY pytest.ini .

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "observatorio.producer"]
