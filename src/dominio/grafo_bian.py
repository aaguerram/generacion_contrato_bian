"""Modelo canónico BIAN: nodos y relaciones tipadas, con procedencia.

Hasta ahora cada adaptador parseaba su fuente a su manera (`CatalogoJson` el Service Landscape,
`CatalogoBianCache` el OpenAPI cacheado, `CatalogoBomPuml` los diagramas) y el pipeline los cruzaba
por nombre normalizado allí donde hacía falta. Eso alcanza para responder "¿qué operaciones tiene
este SD?", pero no para preguntar "¿qué SD están relacionados con este por el propio BOM de BIAN?",
que es lo que necesita la expansión por grafo: sin relaciones explícitas solo quedan heurísticas.

Aquí viven esas entidades y aristas como modelos puros -sin base de datos, sin adaptadores- para
respetar la frontera hexagonal. Un `GrafoBian` se construye desde las fuentes de `docs/` con
`scripts/ingest_bian/` y se consume por un puerto.

Principio que hereda del resto del pipeline: **toda arista lleva su fuente**. Una relación sin
`origen` no se ingesta, porque expandir por una arista inventada es exactamente el error que el
proyecto evita en el resto del flujo (confundir "recuperable" con "aplicable").
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TipoNodo = Literal[
    "SERVICE_DOMAIN",
    "BUSINESS_AREA",
    "BUSINESS_DOMAIN",
    "CONTROL_RECORD",
    "BEHAVIOR_QUALIFIER",
    "OPERATION",
    "SCHEMA",
    "BOM_CLASS",
]

TipoArista = Literal[
    "PERTENECE_A",  # SD -> Business Domain -> Business Area
    "HAS_CR",  # SD -> Control Record
    "HAS_BQ",  # Control Record -> Behavior Qualifier
    "HAS_OPERATION",  # CR/BQ -> Operation
    "RESPONDE_CON",  # Operation -> Schema (response_schema)
    "RECIBE",  # Operation -> Schema (request_schema)
    "MODELA",  # SD -> clase del BOM (PUML)
    "ASOCIA",  # clase BOM -> clase BOM (asociación del diagrama)
    "REFERENCIA",  # Schema -> Schema ($ref entre propiedades)
]

# Un nodo compartido por más de estos Service Domain no discrimina nada: medido sobre el grafo
# real, `Party` la modelan 125 SD y `Arrangement` 88, así que usarlos de puente alcanza medio
# catálogo. Con 8, las clases del BOM que siguen sirviendo de puente son ~1.100 de 1.168 (la
# mediana de una clase es aparecer en 1 solo SD) y se descartan justo las genéricas.
MAX_SD_POR_PUENTE = 8

# Aristas que la expansión por grafo puede recorrer para proponer OTRO Service Domain candidato.
# `PERTENECE_A` queda fuera a propósito: compartir Business Area no dice nada sobre ownership —
# "Sales and Service" tiene decenas de SD sin relación funcional entre sí.
ARISTAS_EXPANDIBLES: tuple[TipoArista, ...] = ("MODELA", "ASOCIA", "REFERENCIA")


class CandidatoGrafo(BaseModel):
    """Un Service Domain propuesto por expansión de grafo, con por dónde se llegó."""

    service_domain: str
    score: float = Field(
        description="Especificidad de la conexión (1/nº de SD que comparten el puente)."
    )
    camino: list[TipoArista] = Field(default_factory=list)
    puentes: list[str] = Field(
        default_factory=list, description="Nodos por los que se llegó (clases BOM, schemas)."
    )


class NodoBian(BaseModel):
    """Una entidad del catálogo BIAN, identificada de forma canónica y estable."""

    id: str = Field(description="Identidad canónica: '<tipo>:<clave normalizada>'.")
    tipo: TipoNodo
    nombre: str = Field(description="Nombre tal cual lo publica la fuente.")
    service_domain: str | None = Field(
        default=None, description="SD al que pertenece el nodo (None en BA/BD)."
    )
    atributos: dict[str, str] = Field(
        default_factory=dict, description="Datos planos de la fuente (tipo, patrón, method/path…)."
    )
    origen: str = Field(description="Archivo de `docs/` del que salió este nodo.")


class AristaBian(BaseModel):
    """Una relación verificada entre dos nodos. Sin `origen` no se ingesta."""

    desde: str
    hasta: str
    tipo: TipoArista
    origen: str = Field(description="Archivo de `docs/` que respalda la relación.")


class GrafoBian(BaseModel):
    """El catálogo BIAN como grafo. Inmutable en la práctica: se reconstruye, no se parchea."""

    release: str = "14.0.0"
    nodos: list[NodoBian] = Field(default_factory=list)
    aristas: list[AristaBian] = Field(default_factory=list)
    incidencias: list[str] = Field(
        default_factory=list,
        description="Referencias colgantes y huecos detectados al ingestar. Nunca se silencian.",
    )

    def indice_nodos(self) -> dict[str, NodoBian]:
        return {n.id: n for n in self.nodos}

    def vecinos(
        self, nodo_id: str, tipos: tuple[TipoArista, ...] | None = None
    ) -> list[tuple[str, TipoArista]]:
        """Vecinos directos en ambos sentidos: una asociación del BOM no tiene dirección útil."""
        permitidos = tipos or ARISTAS_EXPANDIBLES
        salida: list[tuple[str, TipoArista]] = []
        for a in self.aristas:
            if a.tipo not in permitidos:
                continue
            if a.desde == nodo_id:
                salida.append((a.hasta, a.tipo))
            elif a.hasta == nodo_id:
                salida.append((a.desde, a.tipo))
        return salida

    def grado_por_service_domain(self) -> dict[str, int]:
        """En cuántos Service Domain aparece cada nodo compartido (clases del BOM, sobre todo)."""
        cuenta: dict[str, set[str]] = {}
        indice = self.indice_nodos()
        for a in self.aristas:
            if a.tipo != "MODELA":
                continue
            sd = indice[a.desde].service_domain if a.desde in indice else None
            if sd:
                cuenta.setdefault(a.hasta, set()).add(sd)
        return {nid: len(sds) for nid, sds in cuenta.items()}

    def service_domains_alcanzables(
        self,
        service_domain: str,
        *,
        saltos: int = 2,
        max_sd_por_puente: int = MAX_SD_POR_PUENTE,
        tope: int = 10,
    ) -> list[CandidatoGrafo]:
        """Otros SD conectados a este por el propio BOM de BIAN, ordenados por especificidad.

        Es la primitiva de Graph RAG. La ingenuidad de "camina dos saltos y devuelve lo que
        encuentres" no sirve aquí: medido sobre el grafo real, desde `Correspondence` se alcanzan
        **157 de los 341** Service Domains, porque clases genéricas del BOM (`Party` la modelan 125
        SD, `Arrangement` 88, `Agreement` 76) conectan casi todo con casi todo. Un candidato entre
        160 no es una señal, es el catálogo entero.

        Por eso la expansión:
          - **ignora los nodos puente demasiado compartidos** (`max_sd_por_puente`): compartir
            `Party` no dice nada; compartir una clase que solo modelan dos SD sí;
          - **puntúa por rareza del puente** (1/nº de SD que lo comparten, en la línea de un IDF),
            de forma que el orden refleja cuán específica es la conexión;
          - **acumula** cuando dos SD comparten varios puentes raros, que es la señal más fuerte;
          - devuelve el nodo puente y el camino, para que la propuesta sea auditable — igual que
            toda evidencia en este pipeline, una expansión sin fuente no vale.
        """
        indice = self.indice_nodos()
        grado = self.grado_por_service_domain()
        inicio = {n.id for n in self.nodos if n.service_domain == service_domain}
        if not inicio:
            return []

        vistos = set(inicio)
        frontera: list[tuple[str, list[TipoArista], str | None]] = [
            (nid, [], None) for nid in inicio
        ]
        acumulado: dict[str, dict] = {}

        for _ in range(max(0, saltos)):
            siguiente: list[tuple[str, list[TipoArista], str | None]] = []
            for nid, camino, puente in frontera:
                for vecino, tipo in self.vecinos(nid):
                    compartido = grado.get(vecino, 0)
                    if compartido > max_sd_por_puente:
                        continue  # nodo-hub: conecta todo, no discrimina nada
                    ruta = [*camino, tipo]
                    via = puente or (indice[vecino].nombre if vecino in grado else None)
                    nodo = indice.get(vecino)
                    if nodo and nodo.service_domain and nodo.service_domain != service_domain:
                        # Se contabiliza AUNQUE el SD ya se hubiera alcanzado por otro camino:
                        # llegar dos veces por dos puentes raros distintos es la señal más fuerte
                        # que da el grafo, y bloquearlo por "ya visto" la perdía (dos SD con dos
                        # clases en común puntuaban igual que dos con una sola).
                        peso = 1.0 / max(1, grado.get(nid, compartido or 1))
                        dato = acumulado.setdefault(
                            nodo.service_domain,
                            {"score": 0.0, "camino": ruta, "puentes": []},
                        )
                        dato["score"] += peso
                        if via and via not in dato["puentes"]:
                            dato["puentes"].append(via)
                    # La expansión sí evita revisitar: acumular es barato, recorrer no.
                    if vecino not in vistos:
                        vistos.add(vecino)
                        siguiente.append((vecino, ruta, via))
            frontera = siguiente

        candidatos = [
            CandidatoGrafo(
                service_domain=sd,
                score=round(min(1.0, d["score"]), 4),
                camino=d["camino"],
                puentes=d["puentes"][:5],
            )
            for sd, d in acumulado.items()
        ]
        candidatos.sort(key=lambda c: (-c.score, c.service_domain))
        return candidatos[:tope]


def id_nodo(tipo: TipoNodo, *partes: str) -> str:
    """Identidad canónica de un nodo: estable entre corridas y entre releases."""
    from src.dominio.normalizacion import normalizar

    clave = "/".join(normalizar(p) for p in partes if p)
    return f"{tipo.lower()}:{clave}"
