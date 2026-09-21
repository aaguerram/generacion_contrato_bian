# syntax=docker/dockerfile:1.7
# Imagen de la API. Lleva dentro el pipeline completo (`src/` + `docs/`) porque la corrida se
# ejecuta EN PROCESO: la API no es un cliente del mapeo, es su capa de entrada HTTP.
#
# Tres mecanismos de caché, cada uno para un caso distinto:
#   1. El orden de las capas — no cambia nada => no se reinstala nada (caché de capas de Docker).
#   2. `--mount=type=cache` sobre el directorio de pip — cambia UNA dependencia => las demás salen
#      del disco, no de la red. Sin esto, tocar una línea de requirements.txt volvía a descargar
#      las ~300 MB de ruedas enteras: medido, 1 min 56 s.
#   3. Dos capas de dependencias separadas — tocar las 5 de la API no reinstala las del pipeline.
FROM python:3.12-slim

# OJO: aquí NO va PIP_NO_CACHE_DIR. Desactivar la caché de pip vacía el mount del punto 2 y deja
# el mecanismo sin efecto: pip volvería a bajarlo todo de la red en cada reinstalación.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --upgrade pip

# Dependencias del PIPELINE. Es la capa cara (langchain, langgraph, numpy...) y la que casi nunca
# cambia, así que va sola y primero.
COPY requirements.txt /tmp/req/pipeline.txt
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install -r /tmp/req/pipeline.txt

# Dependencias EXCLUSIVAS de la API (fastapi, uvicorn, psycopg). Van en su propia capa: añadir una
# aquí no puede obligar a reinstalar todo lo de arriba.
COPY api/requirements.txt /tmp/req/api.txt
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install -r /tmp/req/api.txt

# `--link` hace cada COPY independiente del anterior: tocar el código NO invalida la capa de 108 MB
# de evidencia, y actualizar la evidencia no obliga a recopiar el código.
COPY --link docs/ /app/docs/
COPY --link src/ /app/src/
COPY --link api/ /app/api/
COPY --link config.yaml /app/config.yaml

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
