# Interfaz web y API — `docker compose`

Dos servicios nuevos sobre el pipeline de siempre, **sin tocarlo**: una API HTTP (`api/`) y una
página React (`frontend/`). El mapeo se sigue ejecutando exactamente como por consola; la API es
solo su capa de entrada.

```bash
docker compose up -d --build      # levantar todo
docker compose logs -f api        # seguir una corrida
docker compose down               # parar (los datos siguen en los volúmenes)
docker compose down -v            # parar y BORRAR la base y el workspace
```

| Servicio   | URL                     | Puerto publicado |
|------------|-------------------------|------------------|
| Página     | http://localhost:5174   | 5174 → 80        |
| API        | http://localhost:8010   | 8010 → 8000      |
| PostgreSQL | `localhost:5434`        | 5434 → 5432      |

Los puertos no son los habituales (5173 / 8000 / 5432) porque esos estaban ocupados en la máquina
de desarrollo. Dentro de la red de compose los servicios se llaman por su nombre (`api`, `db`), así
que cambiar el puerto publicado no afecta a nada interno.

## Caché de construcción: no se vuelve a descargar lo que ya está

Tres mecanismos, cada uno para un caso distinto. Medido en esta máquina:

| Qué cambió                            | Antes     | Ahora  |
|---------------------------------------|-----------|--------|
| Nada                                   | ~1 s      | ~1 s   |
| Código (`src/`, `api/`, `frontend/src`) | ~1 s      | 1-4 s  |
| `requirements.txt` del pipeline        | 1 min 56 s | **11 s** |
| Solo `api/requirements.txt`            | 1 min 56 s | **3 s** |

1. **Orden de las capas.** Las dependencias se copian e instalan ANTES que el código, así que
   editar un `.py` o un componente no reinstala nada. Esto ya estaba.
2. **`--mount=type=cache` sobre el directorio de pip y el de npm.** Es lo que arregla el caso que
   dolía: al cambiar UNA línea de un archivo de dependencias, la capa se invalida entera y el
   gestor reinstala todo. Con la caché montada, ese "todo" sale del disco en vez de la red —
   medido en la reinstalación completa del pipeline: **165 paquetes servidos desde caché, cero
   descargas**. Para que funcione, la imagen de la API **no** puede llevar `PIP_NO_CACHE_DIR`:
   desactivar la caché de pip deja el mount vacío y el mecanismo sin efecto.
3. **Dos capas de dependencias separadas en la API.** Las del pipeline (langchain, langgraph,
   numpy…) van en su propia capa, antes que las cinco de la API (fastapi, uvicorn, psycopg).
   Añadir una dependencia de la API ya no reinstala las del pipeline.

Además, los `COPY --link` hacen cada copia independiente de la anterior: tocar el código no
invalida la capa de 108 MB de evidencia BIAN, ni al revés.

La caché vive en el constructor, no en las imágenes. Si ocupa demasiado:

```bash
docker buildx du                 # cuánto ocupa y cuánto es reclamable
docker buildx prune --filter 'until=168h'   # tirar lo que no se usa hace una semana
```

## Nada se instala en local

`npm` solo corre dentro de la imagen del frontend (etapa `node:22-alpine`), que compila y deja el
resultado servido por nginx. No hace falta Node en la máquina, y no se versiona un
`package-lock.json` precisamente para no obligar a generarlo en local.

Las claves de API se leen de `.env` con `env_file`, así que **no viajan dentro de la imagen**:
rotar una clave es reiniciar el contenedor, no reconstruirlo. Si no hay `.env`, la pila arranca
igual y solo funciona `--proveedor fake`.

## Por qué la ejecución no tiene límite de tiempo

Una corrida real tarda de minutos a decenas de minutos, según cuántas Historias de Usuario, cuántos
candidatos y qué proveedor del failover conteste. Mantener abierta una petición HTTP todo ese rato
es pedirle un timeout a alguien: al navegador, a nginx o al propio servidor. Por eso:

- `POST /api/intentos/{id}/ejecutar` arranca un hilo y devuelve **202 al instante**.
- El cliente pregunta por `/estado` cada 2 s y va viendo el log real.
- nginx tiene `proxy_read_timeout 1h` para las peticiones que sí pueden tardar.
- La API corre con **un solo worker**: las corridas viven en hilos de ESE proceso y su log en
  memoria. Con varios workers, una consulta de estado podría caer en el proceso que no la ejecuta.
  El paralelismo real del pipeline lo da `concurrencia`, no el número de workers.

Cerrar la pestaña no cancela nada: el estado está en Postgres y la corrida sigue en el servidor.

## Dónde viven los datos

| Qué                                   | Dónde                                   |
|---------------------------------------|-----------------------------------------|
| Intentos, resultados, log, validación | PostgreSQL, tabla `intentos` (JSONB)     |
| HU y `funcionalidad.json` de la corrida | volumen `datos-api` en `/datos/<id>/`  |
| Cache BIAN que la corrida descargue   | `./docs/bian-cache` montado desde el repo |

La fuente de verdad es Postgres: el workspace se **regenera** antes de cada corrida, así que
reconstruir la imagen no pierde ningún intento. La cache BIAN se monta desde el repositorio para
que lo que una corrida descargue sobreviva a una reconstrucción.

## Cómo se usa la página

1. **Nuevo intento**: pega todas las Historias de Usuario en una caja y describe la funcionalidad
   macro (nombre + detalle). Es la misma información que pide la consola.
2. **Guardar no ejecuta nada.** El botón de ejecutar aparece después, en el detalle del intento.
3. **Ejecutar** lanza el mapeo y la pestaña de ejecución enseña el log en vivo.
4. **Validación**: opcionalmente sube un `mapeo-historias-service-domains.json` de una corrida ya
   validada. Al terminar la siguiente corrida se compara contra él.

La comparación usa el **mismo criterio que la suite E2E**: Service Domains directos y tentativos, y
sus operaciones por `(operation_id, method, path, tipo, grupo)`. Lo narrativo (razonamiento,
justificación, scores) se ignora a propósito porque cambia entre corridas aunque el resultado de
negocio sea el mismo. Aquí la comparación es **informativa**: lo "inesperado" puede ser cobertura
nueva, solo lo que falta señala una regresión.

## Cómo llegan las historias al pipeline

El caso de uso recibe un **directorio con un archivo por historia**. La lista del formulario es la
forma canónica y se escribe tal cual: un archivo por elemento, en el orden de la lista, con el
título encabezando el contenido. No hay nada que adivinar.

Antes las historias viajaban pegadas en un solo `textarea` y el servidor las partía por marcadores
(una línea de guiones, `## Título`, `HU-01:`). Eso rompía en cuanto el detalle de una historia
llevaba una regla horizontal o un encabezado Markdown, que es justo como se escribe una historia
con criterios de aceptación: el separador la partía por la mitad. El separador sigue en el código
(`api/historias.py`) para **migrar** los intentos guardados con el formato viejo, y esa migración
corre sola al arrancar la API.

## Separación de capas

`api/` no contiene ninguna regla de negocio del mapeo: llama a `crear_caso_uso_mapeo(...)` igual
que el CLI y lee el JSON que el pipeline escribe. El frontend sigue Feature-Sliced Design
(`app → pages → widgets → features → entities → shared`), y los alias de importación hacen visible
la capa de cada import, así que una violación de la regla de dependencias se ve leyendo la línea.

## Diagnóstico

```bash
docker compose ps
docker compose logs api --tail 50
docker compose exec db psql -U contratos -d contratos -c "select id, estado, segundos from intentos;"

# La pila del proceso, sin pararlo (el servicio trae SYS_PTRACE por esto mismo):
docker compose exec api pip install -q py-spy && docker compose exec api py-spy dump --pid 1
```

Ese último comando es el que encontró el interbloqueo del cerrojo del ejecutor: `lanzar()` pedía un
cerrojo no reentrante que ya tenía, y se colgaba la corrida y, detrás, toda consulta de estado.
Cubierto por `tests/unit_test/test_api_ejecutor.py`.
