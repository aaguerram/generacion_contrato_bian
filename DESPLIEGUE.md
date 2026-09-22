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

## Ancho completo y adaptable

La página usa el monitor entero: el contenedor no tiene ancho máximo y el margen lateral crece con
la pantalla (`clamp(1rem, 2.5vw, 2.5rem)`), sin puntos de corte. Lo que sí se limita es la MEDIDA
de lectura de los párrafos largos, y eso se hace bloque a bloque: una tabla de resultados o el
lienzo del grafo sí quieren todo el ancho disponible.

El lienzo del flujo crece con la ventana (`clamp(26rem, 68vh, 58rem)`), que en vertical es lo que
decide a qué escala cabe el grafo entero. Por debajo de 640 px, las cabeceras de tarjeta envuelven
y sus botones pasan a ocupar la línea completa, que además es un tamaño de pulsación decente.

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

- `POST /api/generaciones/{id}/ejecutar` arranca un hilo y devuelve **202 al instante**.
- El cliente pregunta por `/estado` cada 2 s y va viendo el log real.
- nginx tiene `proxy_read_timeout 1h` para las peticiones que sí pueden tardar.
- La API corre con **un solo worker**: las corridas viven en hilos de ESE proceso y su log en
  memoria. Con varios workers, una consulta de estado podría caer en el proceso que no la ejecuta.
  El paralelismo real del pipeline lo da `concurrencia`, no el número de workers.

Cerrar la pestaña no cancela nada: el estado está en Postgres y la corrida sigue en el servidor.
Al volver, la página recupera de la base los pasos que ocurrieron mientras no estabas y sigue
escuchando los nuevos.

Lo que sí corta una corrida es **reiniciar el contenedor de la API**, porque el mapeo vive en un
hilo de ese proceso. Antes la generación se quedaba marcada como `ejecutando` para siempre, con la
insignia girando y el botón de ejecutar bloqueado por su propio fantasma. Ahora el arranque las
reconcilia: un proceso recién nacido no puede tener corridas vivas, así que toda generación que la
base diga `ejecutando` pasa a `fallido` con el motivo, y sus pasos a medias se cierran como
`interrumpido`. Los pasos que sí terminaron se conservan. Esto vale porque la API corre con **un
solo worker**; con varios procesos, arrancar uno mataría las corridas de los otros.

## Ver el flujo mientras corre

La pestaña **Flujo** dibuja el grafo de LangGraph con React Flow. La red entera se ve desde el
principio, apagada, y cada nodo se enciende cuando la corrida entra en él.

- **La topología se lee del grafo real** (`GET /api/grafo`), no está escrita a mano: se compila el
  caso de uso con `--proveedor fake` -- construir el grafo no llama a ningún modelo -- y se le
  pregunta por sus nodos y aristas. Un diagrama mantenido aparte se desincroniza del código en
  cuanto alguien añade un nodo, y un dibujo que miente sobre el flujo es peor que no tenerlo.
- **Vertical, en dos columnas**: el flujo se lee de arriba abajo, con el grafo principal a la
  izquierda y el subgrafo que corre por cada historia a la derecha. `procesar_historia` invoca el
  subgrafo con `.invoke()`, así que esa arista no existe en ninguno de los dos grafos y se declara
  aparte, o el dibujo serían dos islas. Encadenarlos en una sola columna la haría del doble de
  alto y no cabría en pantalla.
- **Un nodo del dibujo por TIPO de nodo, no por ejecución.** Con el abanico de `Send`,
  `evaluar_candidato` corre una vez por candidato: son 28 ejecuciones en un lote de dos historias.
  Se agrupan bajo un nodo con su contador, y el modal lista cada una.
- **Pulsar un nodo abre su detalle** con los datos de entrada y de salida en pestañas, el modelo
  que respondió, el prompt y el tiempo. El JSON se explora en árbol: cada objeto y cada lista se
  pliega, hay búsqueda por clave o valor, y el marco desplaza en los dos ejes. Antes se abría al
  pasar el ratón por encima, y cruzar el lienzo encadenaba modales aunque hubiera un retardo.
- **Mientras corre, la cámara sigue al nodo activo** con zoom legible, y al terminar vuelve a la
  vista completa.

### Detener la corrida en un nodo

En el detalle de cualquier nodo hay un botón para que la corrida se pare al terminarlo. La
siguiente ejecución llega hasta ahí y no ejecuta nada de lo que viene después; la generación queda en
estado `detenido`, que **no** es un fallo.

El corte se pone en el modal y no con un doble clic en el lienzo por una razón concreta: mientras
un `<dialog>` modal está abierto, el resto de la página queda inerte y el doble clic no llegaría
nunca al nodo.

No se usa `interrupt_after` de LangGraph, que sería lo idiomático, porque aquí no funcionaría:
`procesar_historia` invoca el subgrafo con `.invoke()` directo, así que una interrupción dentro
del subgrafo no pausaría el grafo exterior. En su lugar, el observador lanza una señal de parada
después del nodo elegido y la corrida termina ahí. No hay mapeo publicado -- la corrida no llegó
al final --, pero cada paso ya está guardado.

### Por qué eventos del servidor y no un socket

La comunicación es de **una sola dirección**: el servidor cuenta por dónde va y el cliente
escucha. Un canal de eventos del servidor (`GET /api/generaciones/{id}/eventos`) deja menos superficie
expuesta que un socket bidireccional y trae reconexión automática de serie. El cliente manda
`desde` con el último paso que vio y el servidor le rellena el hueco **desde la base**, así que
perder la conexión no cuesta la corrida.

nginx lleva `X-Accel-Buffering: no` en esa respuesta; sin eso bufferizaría los eventos hasta
cerrar la conexión, que es justo lo contrario de lo que hace falta.

### Qué se guarda de cada paso

Una fila por paso en la tabla `eventos_nodo`: nodo, instancia del abanico, estado, datos de
entrada, datos de salida, proveedor, modelo, identificador del prompt, duración y marcas de
tiempo. Es la memoria de la corrida cuando el proceso ya no está: abrir una generación de ayer pinta
su flujo igual que si se acabara de ejecutar.

Los datos se **resumen** antes de guardarlos (`api/serializacion.py`). El estado que circula por
el grafo lleva el catálogo entero de 341 Service Domains, y guardarlo en cada uno de los ~60 pasos
de una corrida serían decenas de copias del mismo catálogo. Lo pesado se sustituye por un marcador
que dice qué había y cuánto ocupaba, nunca desaparece en silencio.

El estado `interrumpido` de un paso significa que ese nodo estaba a mitad cuando la corrida
terminó. Ni terminó ni falló. Sin eso, un corte dejaba filas abiertas para siempre y la interfaz
pintaba esos nodos girando sin fin.

## Dónde viven los datos

| Qué                                   | Dónde                                   |
|---------------------------------------|-----------------------------------------|
| Generaciones, resultados, log, validación | PostgreSQL, tabla `generaciones` (JSONB) |
| Cada paso del grafo de una corrida    | PostgreSQL, tabla `eventos_nodo`         |
| HU y `funcionalidad.json` de la corrida | volumen `datos-api` en `/datos/<id>/`  |
| Cache BIAN que la corrida descargue   | `./docs/bian-cache` montado desde el repo |

La fuente de verdad es Postgres: el workspace se **regenera** antes de cada corrida, así que
reconstruir la imagen no pierde ninguna generación. La cache BIAN se monta desde el repositorio para
que lo que una corrida descargue sobreviva a una reconstrucción.

## Cómo se usa la página

1. **Nueva generación**: pega todas las Historias de Usuario en una caja y describe la funcionalidad
   macro (nombre + detalle). Es la misma información que pide la consola.
2. **Guardar no ejecuta nada.** El botón de ejecutar aparece después, en el detalle de la generación.
3. **Ejecutar** lanza el mapeo y la pestaña de ejecución enseña el log en vivo.
4. **Validación**: opcionalmente sube un `mapeo-historias-service-domains.json` de una corrida ya
   validada. Al terminar la siguiente corrida se compara contra él.
5. **Volver a ejecutar** no ejecuta nada por sí mismo: archiva esta versión y abre una copia.

### Una generación se ejecuta UNA vez

El botón de ejecutar tiene dos caras y solo una está visible, en las pestañas Ejecución y Flujo:

| Estado de la generación        | Botón               | Qué hace                                  |
|--------------------------------|---------------------|-------------------------------------------|
| Nunca ejecutada                | Ejecutar            | Lanza la corrida.                          |
| Ejecutada                      | Volver a ejecutar   | Archiva esta versión y abre una copia.     |
| Archivada (ya cedió su nombre) | ninguno             | Solo se consulta; enlaza a la versión nueva. |

"Volver a ejecutar" **no vuelve a correr encima del resultado anterior**. Le pega al nombre la fecha
de su corrida (`e2e001` pasa a `e2e001-22-09-2026_07:56:21`), deja ese registro congelado con su
resultado, su log y su comparación, y crea uno nuevo con el nombre limpio, las mismas historias, la
misma funcionalidad y las mismas opciones. La página se va a la copia, que es la que tiene el botón
de ejecutar.

El archivo de validación **no** se hereda: se sube en cada versión, a propósito. Arrastrarlo en
silencio haría que la corrida nueva se comparase contra una referencia que quien la lanzó no
eligió.

Así, cada corrida deja su propia prueba de lo que pasó aquel día en vez de machacar la anterior, y
la lista se lee como un historial: el nombre sin fecha es siempre la versión viva. Las archivadas se
distinguen ahí mismo, con el fondo apagado, el borde discontinuo y una etiqueta; el ojo va a las
vivas, que son las que se pueden ejecutar.

La hora del sufijo la pone el servidor, así que el contenedor de la API fija su `TZ` en
`docker-compose.yml`. Sin eso el nombre archivado diría una hora y la ficha de al lado otra, porque
el navegador pinta las fechas en la zona de quien mira.

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
(`api/historias.py`) para **migrar** las generaciones guardadas con el formato viejo, y esa migración
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
docker compose exec db psql -U contratos -d contratos -c "select id, estado, segundos from generaciones;"

# La pila del proceso, sin pararlo (el servicio trae SYS_PTRACE por esto mismo):
docker compose exec api pip install -q py-spy && docker compose exec api py-spy dump --pid 1
```

Ese último comando es el que encontró el interbloqueo del cerrojo del ejecutor: `lanzar()` pedía un
cerrojo no reentrante que ya tenía, y se colgaba la corrida y, detrás, toda consulta de estado.
Cubierto por `tests/unit_test/test_api_ejecutor.py`.
