"""Propiedad de clases del BOM BIAN -> Service Domains candidatos. Puro: solo stdlib + dominio.

La pregunta que resuelve este módulo NO es "¿qué Service Domain habla de esto?" -eso ya lo
intentan el léxico y BM25- sino **"¿quién es el DUEÑO de la clase que la historia necesita?"**.

La respuesta está en el propio modelo BIAN y es binaria. Una misma clase aparece en decenas de
diagramas BOM: en el del Service Domain que la **define** y en el de todos los que solo la
**referencian**. `docs/entity.json` los distingue con una nota del diagrama:

    Party   en Party Reference Data Directory   notes={'BQ': 'Reference', 'AssetType': ...}   6 atributos
    Party   en Location Data Management         notes={'Extensible': 'no',
                                                       'BOMDiagram': 'Party Reference Data Directory BOM Diagram'}   0 atributos

La ocurrencia que **no** lleva `Extensible` es la del dueño; la que la lleva es una caja importada
-normalmente vacía y con un puntero al diagrama de quien sí la define-. Medido sobre el archivo
entero: una clase elegible aparece en **mediana 1 Service Domain** (media 1,46) frente a mediana 2
/ media 6,2 de las que llevan la marca, y **559 de las 634** notas `BOMDiagram` apuntan justo al SD
donde esa clase es elegible. La regla es simétrica: `Location` lleva `Extensible: yes` en Party
Reference Data Directory y es propiedad de Location Data Management.

Solo sirven los diagramas **BOM**: la propiedad `Extensible` no existe en los de Control Record
(1.463 ocurrencias), así que aceptarlos dejaría pasar cualquier clase sin criterio.

Lo que este módulo produce es `Service Domain + Behavior Qualifier`, nunca una operación:
`entity.json` y el Service Landscape no tienen `operationId`/`path`/`method`. Anclar la operación
es trabajo del paso 9 contra `docs/bian-cache/`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from src.dominio.fusion_rrf import fusion_rrf
from src.dominio.historias import CandidatoClaseBom, EvidenciaClaseBom
from src.dominio.vocabulario_bian import CLASES_BOM_POR_TERMINO, EQUIVALENCIAS_RETRIEVAL

_TOKEN = re.compile(r"[a-z0-9]+")
# Ruido estructural del BOM: aparece en el nombre de casi cualquier clase de Control Record
# ("BQ Reference Instance Record") y no discrimina nada.
_VACIAS = frozenset(
    """de del la el los las un una con por para que su sus the of and for to type record instance
    reference number value values data""".split()
)
# Una clase que se llama como su propio Service Domain ("Party Reference Data Directory Entry")
# es la raíz del diagrama: emparejarla es casi emparejar el NOMBRE del SD, que es justo lo que ya
# hace el nodo 2b. Cuenta, pero a mitad de precio.
_PESO_CLASE_ECO = 0.5
_PESO_NOMBRE = 2.0
_PESO_ATRIBUTO = 1.0
# Un valor de enum es una cita literal del modelo ("EmailAddress", "MobileNumber"): es la
# evidencia más específica que da el BOM, y la única que nombra el dato de negocio tal cual.
_PESO_ENUM = 2.0


def tokenizar_consulta(textos: Iterable[str]) -> set[str]:
    """Tokens de la HU traducidos al vocabulario del BOM (1 término ES -> N términos EN).

    `bm25.tokenizar` traduce 1:1 y no sirve aquí: el corpus del BOM dice `email`/`cell`, no `mail`,
    y la clase que modela a un cliente se llama `Party`, no `Customer`.
    """
    salida: set[str] = set()
    for texto in textos:
        plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
        for t in _TOKEN.findall(plano.lower()):
            if t in _VACIAS or len(t) <= 2:
                continue
            salida |= CLASES_BOM_POR_TERMINO.get(t, {EQUIVALENCIAS_RETRIEVAL.get(t, t)})
    return salida


def _tokens(nombre: str) -> set[str]:
    plano = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    return {t for t in _TOKEN.findall(plano.lower()) if t not in _VACIAS and len(t) > 2}


@dataclass(frozen=True)
class AtributoClase:
    nombre: str
    tipo: str = ""


@dataclass(frozen=True)
class OcurrenciaClase:
    """Una clase tal como aparece en el diagrama de UN Service Domain."""

    service_domain: str
    diagrama: str = "bom"  # "bom" | "control_record"
    kind: str = "class"  # "class" | "enum"
    extensible: str | None = None  # notes.Extensible: "yes" | "no" | None (= dueño)
    bq: str = ""  # notes.BQ -> Behavior Qualifier al que pertenece la clase
    control_record: str = ""  # notes.ControlRecord
    asset_type: str = ""  # notes.AssetType
    bom_de: str = ""  # notes.BOMDiagram -> diagrama del dueño, si la importa
    atributos: tuple[AtributoClase, ...] = ()
    valores_enum: tuple[str, ...] = ()

    @property
    def es_dueno(self) -> bool:
        """El SD DEFINE la clase: está en su BOM y no la marcó como importada del modelo genérico."""
        return self.diagrama == "bom" and self.extensible is None


@dataclass(frozen=True)
class ClaseBian:
    nombre: str
    ocurrencias: tuple[OcurrenciaClase, ...] = ()
    # Del modelo genérico (`bian_bom` en entity.json): la definición en prosa de la clase y los
    # nombres de sus propiedades. No deciden la propiedad -eso lo dicen las ocurrencias-, pero son
    # el texto con el que un canal denso puede reconocer la clase desde una HU en español.
    descripcion: str = ""
    propiedades: tuple[str, ...] = ()

    def duenos(self) -> list[OcurrenciaClase]:
        return [o for o in self.ocurrencias if o.es_dueno]

    def importada_en(self) -> list[str]:
        return [o.service_domain for o in self.ocurrencias if o.diagrama == "bom" and not o.es_dueno]


@dataclass(frozen=True)
class ClaseRequerida:
    """Clase del BOM que la historia necesita, con por qué se la considera necesaria."""

    clase: str
    peso: float
    motivos: tuple[str, ...] = ()


def _nota_de_enum(
    clase: str,
    enum: str,
    valores: Sequence[str],
    adicionales: Sequence[str],
) -> str:
    """La nota que necesita el paso 3: ¿la clase del enum guarda además el VALOR?

    Un enum solo TIPIFICA. `Contact Point` dice que un Party tiene un punto de contacto de tipo
    `Electronic Address` o `Phone Number`, pero no guarda ninguno de los dos; `Phone Address` sí
    guarda `Phone Number`. Sin esta distinción los dos Service Domains parecen aportar lo mismo, y
    la decisión de completitud se toma a ciegas.
    """
    if not enum:
        return ""
    muestra = ", ".join(valores[:4]) + ("..." if len(valores) > 4 else "")
    if adicionales:
        return (
            f"'{clase}' tipifica con el enum {enum} ({muestra}) Y guarda "
            f"{len(adicionales)} atributo(s) con valor: {', '.join(adicionales)}"
        )
    return (
        f"'{clase}' SOLO tipifica con el enum {enum} ({muestra}): "
        f"sin atributos adicionales, no guarda el valor"
    )


def valores_por_enum(clases: Mapping[str, ClaseBian]) -> dict[str, tuple[str, ...]]:
    """`{nombre de enum: valores}`. Los valores son idénticos en todos los diagramas que lo dibujan."""
    salida: dict[str, tuple[str, ...]] = {}
    for nombre, clase in clases.items():
        for o in clase.ocurrencias:
            if o.kind == "enum" and o.valores_enum and nombre not in salida:
                salida[nombre] = o.valores_enum
    return salida


def clases_requeridas(
    terminos: Sequence[str] | set[str],
    clases: Mapping[str, ClaseBian],
    *,
    nombres_enum: frozenset[str] | set[str] = frozenset(),
    tope: int = 12,
) -> list[ClaseRequerida]:
    """Qué clases del BOM pide la historia. Solo clases con dueño: sin dueño no hay candidato.

    Un **enum no es candidato**: no es un objeto de negocio, es la tipificación de uno. Sus valores
    sí cuentan, pero como evidencia de la clase que lo usa -`Contact Point` vale por decir
    `Electronic Address`/`Phone Number`, no `ContactPointTypeValues` por llamarse así-.
    """
    consulta = set(terminos)
    enums = valores_por_enum(clases)
    marcador: dict[str, float] = {}
    motivos: dict[str, set[str]] = {}
    for nombre, clase in clases.items():
        duenos = [o for o in clase.duenos() if o.kind != "enum"]
        if not duenos or es_artefacto_del_metamodelo(nombre):
            continue
        peso = 0.0
        vistos: set[str] = set()
        eco = any(_tokens(nombre) >= _tokens(o.service_domain) for o in duenos if o.service_domain)
        for w in _tokens(nombre) & consulta:
            peso += _PESO_NOMBRE * (_PESO_CLASE_ECO if eco else 1.0)
            vistos.add(f"nombre:{w}")
        for o in duenos:
            for a in o.atributos:
                # Un atributo cuyo tipo es un enum no aporta valor propio: lo aporta el enum.
                for w in _tokens(a.nombre) & consulta:
                    if f"attr:{w}" not in vistos:
                        peso += _PESO_ATRIBUTO * (0.5 if a.tipo in nombres_enum else 1.0)
                        vistos.add(f"attr:{w}")
                for v in enums.get(a.tipo, ()):
                    for w in _tokens(v) & consulta:
                        if f"enum:{w}" not in vistos:
                            peso += _PESO_ENUM
                            vistos.add(f"enum:{w}")
        if peso > 0:
            marcador[nombre] = peso
            motivos[nombre] = vistos
    ordenadas = sorted(marcador.items(), key=lambda kv: (-kv[1], kv[0]))[:tope]
    return [ClaseRequerida(n, round(p, 2), tuple(sorted(motivos[n]))) for n, p in ordenadas]


def candidatos_por_propiedad(
    requeridas: Sequence[ClaseRequerida],
    clases: Mapping[str, ClaseBian],
    *,
    nombres_enum: frozenset[str] | set[str] = frozenset(),
    tope: int = 8,
) -> list[CandidatoClaseBom]:
    """Cada clase requerida vota, con su peso ENTERO, por cada Service Domain que la DEFINE.

    No se reparte entre dueños: si el modelo BIAN dice que dos SD definen la clase, los dos son
    candidatos legítimos y castigar a ambos por compartirla dejaba fuera al correcto -medido en
    la corrida real del E2E 1: `Contact Point` (Legal Entity Directory + Party Reference Data
    Directory) a 0.5 cada uno, y el dueño del dato cortado por el tope-. La ambigüedad no se
    esconde: viaja en `compartida_con`, para que quien evalúe sepa que hay que elegir.
    """
    enums = valores_por_enum(clases)
    puntos: dict[str, float] = {}
    evidencias: dict[str, list[EvidenciaClaseBom]] = {}
    for req in requeridas:
        clase = clases.get(req.clase)
        if clase is None:
            continue
        duenos = [o for o in clase.duenos() if o.kind != "enum"]
        if not duenos:
            continue
        for o in duenos:
            enum, valores = "", ()
            for a in o.atributos:
                if a.tipo in nombres_enum:
                    enum, valores = a.tipo, enums.get(a.tipo, ())
                    break
            adicionales = tuple(a.nombre for a in o.atributos if a.tipo not in nombres_enum)
            puntos[o.service_domain] = puntos.get(o.service_domain, 0.0) + req.peso
            evidencias.setdefault(o.service_domain, []).append(
                EvidenciaClaseBom(
                    clase=clase.nombre,
                    bq=o.bq,
                    control_record=o.control_record,
                    motivos=list(req.motivos),
                    enum=enum,
                    valores_enum=list(valores),
                    atributos_adicionales=list(adicionales),
                    compartida_con=[d.service_domain for d in duenos if d is not o],
                    importada_en=clase.importada_en()[:6],
                    nota=_nota_de_enum(clase.nombre, enum, valores, adicionales),
                )
            )
    ordenados = sorted(puntos.items(), key=lambda kv: (-kv[1], kv[0]))[:tope]
    return [
        CandidatoClaseBom(service_domain=sd, score=round(p, 2), evidencias=evidencias[sd])
        for sd, p in ordenados
    ]


# ── Paso 1 como recuperación híbrida ─────────────────────────────────────────────────────────
#
# `clases_requeridas` resuelve el paso 1 con un diccionario a mano (`CLASES_BOM_POR_TERMINO`): si
# la HU dice "cliente" y el diccionario no dice `party`, la clase no aparece y el dueño tampoco.
# Lo de abajo convierte ese paso en un problema de RECUPERACIÓN sobre un corpus de clases: un
# documento por clase con dueño, consultado por uno o más canales (BM25 sobre el texto traducido,
# embeddings multilingües sobre el texto natural, el diccionario como un canal más) y fusionado
# con RRF. La propiedad (pasos 2-4) no cambia: sigue votando `candidatos_por_propiedad`.


# Cajas del METAMODELO BIAN que aparecen en algunos diagramas BOM como si fueran clases: las
# operaciones del SD y las etapas de su ciclo de vida (`X_SD_Operations`, `X_Instantiation`,
# `X_Invocation`, `X_Reporting`, `X_ Analytics Object`). No son objetos de negocio -medido sobre
# entity.json: 40 clases, cero atributos, cero descripción-, pero tienen dueño, así que un canal
# denso las recupera por el nombre del SD que llevan pegado y mete al SD entero como candidato.
_ARTEFACTO_METAMODELO = re.compile(
    r"_\s*(SD_)?(Operations|Instantiation|Invocation|Reporting|Analytics Object)$", re.IGNORECASE
)


def es_artefacto_del_metamodelo(nombre: str) -> bool:
    return bool(_ARTEFACTO_METAMODELO.search(nombre or ""))


def _es_candidata(clase: ClaseBian) -> bool:
    """Tiene un dueño que no es enum y no es una caja del metamodelo."""
    return any(o.kind != "enum" for o in clase.duenos()) and not es_artefacto_del_metamodelo(
        clase.nombre
    )


@dataclass(frozen=True)
class ConsultaClases:
    """La misma pregunta en las dos formas que necesitan los canales.

    `texto` es la HU tal como habla el negocio (español): lo que lee un modelo de embeddings
    multilingüe. `terminos` es esa HU ya traducida al vocabulario del BOM (`tokenizar_consulta`):
    lo que necesita un índice léxico cuyo corpus está entero en inglés.
    """

    texto: str
    terminos: frozenset[str] = frozenset()

    @classmethod
    def desde_textos(cls, textos: Iterable[str]) -> "ConsultaClases":
        textos = [t for t in textos if t]
        return cls(texto=". ".join(textos), terminos=frozenset(tokenizar_consulta(textos)))

    @property
    def terminos_texto(self) -> str:
        return " ".join(sorted(self.terminos))


@dataclass(frozen=True)
class CandidatoClase:
    """Una clase del BOM que un canal de recuperación propone, con su score en la escala del canal."""

    clase: str
    score: float = 0.0


def documento_de_clase(
    clase: ClaseBian,
    *,
    nombres_enum: frozenset[str] | set[str] = frozenset(),
    enums: Mapping[str, Sequence[str]] | None = None,
) -> str:
    """El texto por el que se recupera una clase: SU modelo, no el del Service Domain.

    Nombre, definición del modelo genérico, propiedades, atributos de las ocurrencias dueñas y los
    valores de los enums con que tipifica (`Electronic Address`, `MobileNumber`: la cita más
    literal que da el BOM al dato de negocio). A propósito NO lleva el nombre del Service Domain:
    emparejar nombres de SD es trabajo del nodo 2b y de `RecuperadorLexico`; este canal existe
    para llegar al SD por la clase, no por su nombre.
    """
    enums = enums or {}
    partes: list[str] = [clase.nombre]
    if clase.descripcion:
        partes.append(clase.descripcion)
    partes.extend(clase.propiedades)
    vistos: set[str] = set()
    for o in clase.duenos():
        if o.kind == "enum":
            continue
        if o.bq:
            partes.append(o.bq)
        for a in o.atributos:
            if a.nombre and a.nombre not in vistos:
                partes.append(a.nombre)
                vistos.add(a.nombre)
            if a.tipo in nombres_enum:
                for v in enums.get(a.tipo, ()):
                    if v not in vistos:
                        partes.append(v)
                        vistos.add(v)
    return ". ".join(p for p in partes if p)


def documentos_indexables(
    clases: Mapping[str, ClaseBian],
    *,
    nombres_enum: frozenset[str] | set[str] = frozenset(),
) -> list[tuple[str, str]]:
    """`[(nombre de clase, documento)]` SOLO para clases con dueño que no son enums.

    Es el mismo filtro que aplica `clases_requeridas`: una clase sin dueño no lleva a ningún
    Service Domain, y un enum tipifica pero no es un objeto de negocio. Indexar lo demás solo
    añadiría documentos que nunca pueden convertirse en candidato.
    """
    enums = valores_por_enum(clases)
    return [
        (nombre, documento_de_clase(clase, nombres_enum=nombres_enum, enums=enums))
        for nombre, clase in clases.items()
        if _es_candidata(clase)
    ]


def clases_requeridas_desde_rankings(
    rankings: Mapping[str, Sequence[str]],
    clases: Mapping[str, ClaseBian],
    *,
    k: int = 20,
    pesos: Mapping[str, float] | None = None,
    tope: int = 12,
) -> list[ClaseRequerida]:
    """Fusiona con RRF los rankings de clases de varios canales -> clases requeridas.

    `rankings` = `{nombre del canal: [clases ordenadas, mejor primero]}`. El peso de cada clase es
    su score RRF reescalado para que el top-1 de un canal con peso 1.0 valga 1.0 -así
    `candidatos_por_propiedad` reparte y suma en una escala legible-. Los `motivos` dicen qué canal
    la propuso y en qué posición, que es lo que hace auditable la fusión.

    Se descarta lo que no lleva a un dueño (misma regla que `clases_requeridas`): un canal denso
    puede recuperar una clase importada o un enum, y eso no es candidato.
    """
    nombres = [n for n in rankings if rankings[n]]
    if not nombres:
        return []
    lista_pesos = [float((pesos or {}).get(n, 1.0)) for n in nombres]
    fusion = fusion_rrf([list(rankings[n]) for n in nombres], k=k, pesos=lista_pesos)
    escala = float(k + 1)
    salida: list[ClaseRequerida] = []
    for nombre, score in fusion:
        clase = clases.get(nombre)
        if clase is None or not _es_candidata(clase):
            continue
        motivos = tuple(
            f"{canal}#{list(rankings[canal]).index(nombre) + 1}"
            for canal in nombres
            if nombre in rankings[canal]
        )
        salida.append(ClaseRequerida(nombre, round(score * escala, 4), motivos))
        if len(salida) >= tope:
            break
    return salida
