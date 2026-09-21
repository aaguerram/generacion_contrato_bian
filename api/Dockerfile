# Imagen de la API. Lleva dentro el pipeline completo (`src/` + `docs/`) porque la corrida se
# ejecuta EN PROCESO: la API no es un cliente del mapeo, es su capa de entrada HTTP.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Las dependencias van antes que el código: cambiar un .py no reinstala 300 MB de ruedas.
# Por separado y con nombres distintos: un COPY con varios orígenes aplana las rutas, y los dos
# archivos se llaman igual, así que el segundo pisaba al primero.
COPY requirements.txt /tmp/req/pipeline.txt
COPY api/requirements.txt /tmp/req/api.txt
RUN pip install --upgrade pip \
 && pip install -r /tmp/req/pipeline.txt -r /tmp/req/api.txt \
 && rm -rf /tmp/req

# Evidencia BIAN. Es la capa más pesada (~108 MB) y la que menos cambia, así que va sola.
COPY docs/ /app/docs/

COPY src/ /app/src/
COPY api/ /app/api/
COPY config.yaml /app/config.yaml

# El workspace (HU materializadas, funcionalidad.json, salidas) es un volumen: los datos de las
# corridas no pertenecen a la imagen.
ENV API_WORKSPACE=/datos
RUN mkdir -p /datos

EXPOSE 8000

# UN worker a propósito: las corridas viven en hilos de ESTE proceso y su log en memoria. Con
# varios workers una petición de estado podría caer en el proceso que no ejecuta la corrida.
# El paralelismo real del pipeline lo da `concurrencia`, no el número de workers.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--timeout-keep-alive", "120"]
