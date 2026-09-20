"""Adaptador: el analista BIAN LLM del mapeo Historias -> Service Domains.

Un método por nodo del subgrafo. Cada llamada:
  - construye el prompt SOLO con la evidencia recibida (catálogo local / paquete cerrado);
  - pide salida estructurada (pydantic) al chat model con failover;
  - adjunta `MetadatosPrompt` (prompt_id + versión + SHA-256 del texto + modelo + SHA del catálogo)
    para reproducibilidad;
  - NO decide score ni estado final: eso es determinista (capa de dominio).
"""

from __future__ import annotations

import hashlib
import logging
import time

from src.adaptadores.salida.formato_bom import formatear_bom_puml, formatear_schemas_bom
from src.adaptadores.salida.llm.failover import PeticionDemasiadoGrande, SoportaStructured
from src.adaptadores.salida.prompts_mapeo import (
    SPEC_ADVERSARIAL,
    SPEC_CANDIDATOS,
    SPEC_CANDIDATOS_BOM,
    SPEC_CANDIDATOS_GRUPO,
    SPEC_CANDIDATOS_GRUPO_BOM,
    SPEC_COMPLETITUD,
    SPEC_ENRUTAMIENTO,
    SPEC_EVALUACION,
    SPEC_INTENCION,
    SPEC_RECONCILIACION,
    PromptSpec,
)
from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.dominio.historias import (
    CandidatosHistoriaLLM,
    EnrutamientoDominiosLLM,
    EvaluacionCandidatoLLM,
    FuncionalidadMacro,
    HistoriaUsuario,
    IntencionHistoriaLLM,
    MetadatosPrompt,
    PaqueteEvidenciaCandidato,
    ReconciliacionFuncionalidadLLM,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
    ServiceDomainsDeHistoria,
)
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar

logger = logging.getLogger(__name__)

_ROL_MAX_CHARS = 600
# "Sin recorte": un tope tan alto que `_recortar` nunca corta. Es lo que usa la etapa 2b del
# routing jerárquico -- con el catálogo ya acotado a unos 30 SD, el texto entero de cada uno
# (~189 tokens) cuesta menos que los 341 con el rol mutilado.
_SIN_RECORTE = 10**9
# Suelo del último escalón de degradación: el índice mínimo con el que el paso 2 siempre cupo.
_ROL_MIN_CHARS = 240
# La documentación de un nodo de la jerarquía BIAN: 490 chars el más largo, así que el tope no
# recorta nada hoy -- está para que un landscape futuro no se lleve el presupuesto por delante.
_TAXONOMIA_MAX_CHARS = 600
# El Service Role que ven `evaluar_candidato` y `revisar_adversarial`. Tiene que ser el MISMO
# en los dos: el revisor emite DIRECTO_SIN_SERVICE_ROLE ("el Service Role no describe
# verbo+objeto de la historia") sobre la decision del evaluador, asi que si ve menos rol que
# el, contradice con menos evidencia de la que se uso para decidir. Con el limite viejo del
# revisor (120) el corte alcanzaba al 90% de los 341 SD (mediana 309 chars, p90 563) y partia
# la frase justo antes del objeto de negocio: "Party Reference Data Directory" se cortaba en
# "...wide range of party reference data that might ", ocultando "contact details ...
# demographic details", y quedaba marcado DIRECTO_SIN_SERVICE_ROLE pese a tener score 1.0.
_ROL_REVISION_MAX_CHARS = 900


class _CadenaMedida:
    """Envoltorio de diagnóstico: mide cuánto tarda cada llamada LLM real y lo deja en el log
    (nodo = `spec.id`, p.ej. "mapeo.evaluacion") -- para poder auditar latencia por paso sin
    tener que inferirla de los timestamps de httpx."""

    def __init__(self, runnable, nodo: str) -> None:
        self._runnable = runnable
        self._nodo = nodo

    def invoke(self, *args, **kwargs):
        inicio = time.monotonic()
        try:
            return self._runnable.invoke(*args, **kwargs)
        finally:
            logger.info("TIEMPO_LLM nodo=%s tardo=%.1fs", self._nodo, time.monotonic() - inicio)


def _recortar(texto: str, limite: int) -> str:
    t = " ".join((texto or "").split())
    return t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "..."


def _lista(xs: list[str] | tuple[str, ...], vacio: str = "(ninguno)") -> str:
    xs = [x.strip() for x in xs if x and x.strip()]
    return "; ".join(xs) if xs else vacio


def formatear_catalogo(
    catalogo: list[EntradaCatalogo],
    rol_max_chars: int = _ROL_MAX_CHARS,
    chars_negocio: int = 0,
) -> str:
    """Una línea por SD: - "Nombre" · Area > Domain · [Patrón/AssetType] :: rol recortado.

    `chars_negocio > 0` activa el escalón **CAG** (Cache-Augmented Generation): añade a cada SD su
    vocabulario de negocio —`examples_of_use` y `features`— dentro de ese presupuesto de
    caracteres. Es lo que convierte al catálogo del prompt en la fuente completa en vez de un
    índice: a 341 Service Domains el catálogo entero cabe en contexto, así que el candidato
    correcto no puede quedarse fuera por un recorte de recuperación (el Recall@K deja de ser una
    restricción y pasa a ser una elección). El coste es tokens, y por eso es escalonado: el propio
    valor fija el escalón (0 = como siempre, 300 ≈ 25k tokens de más, ~1200 = todo lo que el
    landscape publica).

    Por qué `examples_of_use`/`features` y no el `role_definition` más largo: una HU rara vez
    repite el rol formal ("administer and execute..."), pero sí menciona el escenario y la
    capacidad concreta — es el mismo razonamiento que ya sostiene `texto_para_indexar()`.
    """
    lineas = []
    for e in catalogo:
        jer = " > ".join(p for p in (e.business_area, e.business_domain) if p)
        clasif = " / ".join(p for p in (e.functional_pattern, e.asset_type) if p)
        partes = [f'- "{e.service_domain}"']
        if jer:
            partes.append(f" · {jer}")
        if clasif:
            partes.append(f" · [{clasif}]")
        rol = _recortar(e.service_role or "", rol_max_chars)
        if rol:
            partes.append(f" :: {rol}")
        if chars_negocio > 0:
            negocio = " ".join(t for t in (e.examples_of_use, e.features) if t)
            recortado = _recortar(negocio, chars_negocio)
            if recortado:
                partes.append(f" | {recortado}")
        lineas.append("".join(partes))
    return "\n".join(lineas)


def formatear_taxonomia(
    catalogo: list[EntradaCatalogo], totales_por_dominio: dict[str, int] | None = None
) -> str:
    """La jerarquía BIAN CON su definición, deduplicada y enviada UNA vez.

    `totales_por_dominio` (nombre del Business Domain -> nº REAL de SD en el landscape) existe
    desde que el nodo 2a puede AÑADIR un Service Domain suelto al catálogo enrutado (propietario
    de una clase BOM que la historia necesita). Sin él, un dominio abierto por un solo rescate
    salía como `"Loans and Deposits" (1 SD)` -medido el 2026-09-20 con Savings Account-, que le
    dice al modelo que el dominio es diminuto cuando lo que pasa es que solo ve una parte. Con los
    totales, la etiqueta dice `(1 de 12 SD visibles)`; si el dominio está entero, `(12 SD)` como
    siempre.

    Cada línea de `formatear_catalogo` lleva `· Sales and Service > Customer Management`, pero
    hasta ahora esa jerarquía viajaba como una etiqueta sin definir -- y pesa en el score del paso
    de clasificación. El landscape sí documenta cada nodo (`business_areas[].documentation` y el
    de cada Business Domain); `CatalogoJson` lo arrastra hasta `EntradaCatalogo`.

    Va aparte y no inline por SD por una razón de presupuesto: son 5 áreas + 36 dominios, así que
    deduplicado cuesta ~2.9k tokens y repetido en las 341 líneas del catálogo costaría ~23k -- 8x
    más por exactamente la misma información.
    """
    areas: dict[str, str] = {}
    dominios: dict[str, dict[str, tuple[str, int]]] = {}
    for e in catalogo:
        area = e.business_area
        if not area:
            continue
        areas.setdefault(area, e.business_area_doc or "")
        if e.business_domain:
            por_area = dominios.setdefault(area, {})
            doc, n = por_area.get(e.business_domain, (e.business_domain_doc or "", 0))
            por_area[e.business_domain] = (doc, n + 1)

    lineas = []
    for area, doc in areas.items():
        lineas.append(f'- Business Area "{area}"' + (f" :: {_recortar(doc, _TAXONOMIA_MAX_CHARS)}" if doc else ""))
        for dominio, (doc_dom, n) in dominios.get(area, {}).items():
            sufijo = f" :: {_recortar(doc_dom, _TAXONOMIA_MAX_CHARS)}" if doc_dom else ""
            total = (totales_por_dominio or {}).get(dominio)
            conteo = f"{n} de {total} SD visibles" if total and total > n else f"{n} SD"
            lineas.append(f'  - Business Domain "{dominio}" ({conteo}){sufijo}')
    return "\n".join(lineas)


def formatear_propietarios_bom(candidatos) -> str:
    """El bloque `<propietarios_bom>` del prompt 1.2.0 de candidatos: una entrada por Service
    Domain que el canal de propiedad de clases BOM del nodo 2a propuso, con la evidencia que lo
    sostiene. Hechos del modelo, sin adjetivos: "define X [BQ Y]: nota" -- el LLM decide.
    """
    lineas = []
    for c in candidatos:
        clases = []
        for e in c.evidencias:
            # Una clase que solo aporta su NOMBRE ("define Party Routing Profile") no es evidencia
            # de nada: medido, 2b la tomó como argumento y propuso ese SD. Fuera del bloque.
            if not (e.bq or e.control_record or e.nota or e.atributos_adicionales):
                continue
            pieza = f'"{e.clase}"'
            if e.bq:
                pieza += f" [BQ {e.bq}]"
            elif e.control_record:
                pieza += f" [CR {e.control_record}]"
            if e.nota:
                pieza += f": {e.nota}"
            elif e.atributos_adicionales:
                pieza += f": atributos {', '.join(e.atributos_adicionales[:6])}"
            if e.compartida_con:
                pieza += f" (compartida_con: {', '.join(e.compartida_con)})"
            clases.append(pieza)
        if clases:
            lineas.append(f'- "{c.service_domain}" define ' + "; ".join(clases))
    return "\n".join(lineas)


def _formatear_indice_global(
    catalogo: list[EntradaCatalogo], rol_max_chars: int = 90, chars_negocio: int = 0
) -> str:
    """Índice global compacto (nombre + rol muy recortado) para el hint de completitud.

    Con `chars_negocio > 0` (escalón CAG) el hint deja de ser solo nombres: el revisor de
    completitud ve también con qué vocabulario habla cada Service Domain, que es justo lo que
    necesita para decir "falta este" sin haberlo recuperado antes.
    """
    lineas = []
    for e in catalogo:
        partes = [f'- "{e.service_domain}"']
        rol = _recortar(e.service_role or "", rol_max_chars)
        if rol:
            partes.append(f" :: {rol}")
        if chars_negocio > 0:
            negocio = " ".join(t for t in (e.examples_of_use, e.features) if t)
            recortado = _recortar(negocio, chars_negocio)
            if recortado:
                partes.append(f" | {recortado}")
        lineas.append("".join(partes))
    return "\n".join(lineas)


def _schemas_de_operaciones(operaciones) -> set[str]:
    """Nombres normalizados de request/response schema de `operaciones` — para que
    `formatear_schemas_bom(priorizar=...)` nunca deje fuera, por un corte alfabético, el schema
    que de verdad sostiene (o descarta) un candidato con muchas operaciones/schemas."""
    return {
        normalizar(s)
        for o in operaciones
        for s in (getattr(o, "request_schema", ""), getattr(o, "response_schema", ""))
        if s
    }


def _formatear_operaciones(operaciones) -> str:
    if not operaciones:
        return "  (sin operaciones oficiales en la evidencia)"
    filas = []
    for o in operaciones:
        esquema = " / ".join(p for p in (
            f"req={o.request_schema}" if getattr(o, "request_schema", "") else "",
            f"resp={o.response_schema}" if getattr(o, "response_schema", "") else "",
        ) if p)
        padre = f" <- {o.parent_control_record}" if getattr(o, "parent_control_record", None) else ""
        filas.append(
            f"  - {o.operation_id}  ({o.method} {o.path})  [{o.tipo} {o.grupo}{padre}]"
            + (f"  {esquema}" if esquema else "")
            + (f"  :: {_recortar(o.summary, 90)}" if o.summary else "")
        )
    return "\n".join(filas)




class AnalistaMapeoBianLangChain(AnalistaMapeoBianPort):
    def __init__(
        self,
        chat_model: SoportaStructured,
        *,
        modelo_desc: str = "",
        temperature: float | None = None,
        catalog_sha256: str = "",
        rol_max_chars: int = _ROL_MAX_CHARS,
        cag_chars_por_sd: int = 0,
        chats_por_nodo: dict | None = None,
    ) -> None:
        self._chat = chat_model
        # Un chat distinto para nodos concretos (clave = `prompt_id`). Vacío = todos los nodos
        # comparten la misma cadena, que es el comportamiento de siempre.
        self._chats_por_nodo = dict(chats_por_nodo or {})
        self._modelo_desc = modelo_desc
        self._temperature = temperature
        self._catalog_sha256 = catalog_sha256
        self._rol_max_chars = rol_max_chars
        # 0 = índice de siempre; >0 = escalón CAG (ver `formatear_catalogo`).
        self._cag_chars_por_sd = max(0, cag_chars_por_sd)

    def _escalones_catalogo(self, *, texto_completo: bool = False) -> list[tuple[int, int]]:
        """Presupuestos decrecientes del catálogo `(chars_negocio, rol_max_chars)`.

        Con `texto_completo` (etapa 2b del routing jerárquico) se antepone un escalón SIN recorte:
        el catálogo ya viene acotado a los Service Domains de los dominios enrutados, así que
        caben enteros -- rol completo + `examples_of_use` + `features`, que es justo lo que la
        escalera borraba y nadie veía nunca. Los escalones de siempre quedan DEBAJO como red: si
        el router eligiera media taxonomía, se degrada en vez de morir.

        Primero se recorta el vocabulario de negocio (el escalón CAG) y solo al final el Service
        Role, porque el rol es la señal más discriminante: es lo último que se sacrifica.

        El último escalón es siempre `(0, 240)` — el índice mínimo histórico, ~27k tokens con 341
        SD. Existe porque subir `rol_max_chars` sube el SUELO del prompt: sin este escalón, un
        catálogo que no cabe en ningún modelo deja la HU sin candidatos en vez de degradarse.
        """
        negocio = (
            sorted({self._cag_chars_por_sd, self._cag_chars_por_sd // 2, 0}, reverse=True)
            if self._cag_chars_por_sd
            else [0]
        )
        escalones = [(c, self._rol_max_chars) for c in negocio]
        if self._rol_max_chars > _ROL_MIN_CHARS:
            escalones.append((0, _ROL_MIN_CHARS))
        if texto_completo:
            escalones.insert(0, (_SIN_RECORTE, _SIN_RECORTE))
        return escalones

    # ── infra ────────────────────────────────────────────────────────────────
    def _chat_de(self, spec: PromptSpec):
        return self._chats_por_nodo.get(spec.id, self._chat)

    def _invocar_reduciendo(
        self, spec: PromptSpec, schema, entradas, escalones: list[tuple[int, int]]
    ):
        """Invoca el nodo y, si NINGÚN modelo acepta la petición por tamaño, la reduce y reintenta.

        `escalones` son presupuestos decrecientes del catálogo `(chars_negocio, rol_max_chars)`.
        Cambiar de modelo no arregla un prompt que no cabe en ninguno: lo único que lo arregla es
        mandar menos. Se degrada el CONTENIDO antes que rendirse, y se deja constancia en el log
        de con qué escalón se consiguió — un candidato encontrado con el catálogo recortado no es
        lo mismo que uno encontrado con el catálogo completo.
        """
        ultimo: PeticionDemasiadoGrande | None = None
        for presupuesto in escalones:
            try:
                return self._cadena(spec, schema).invoke(entradas(presupuesto))
            except PeticionDemasiadoGrande as exc:
                ultimo = exc
                logger.warning(
                    "%s: ningún modelo acepta el prompt con (chars_negocio, rol)=%s (%s); reduzco",
                    spec.id, presupuesto, exc,
                )
        assert ultimo is not None
        raise ultimo

    def _cadena(self, spec: PromptSpec, schema):
        chat = self._chat_de(spec)
        return _CadenaMedida(spec.template | chat.with_structured_output(schema), spec.id)

    def _huella(
        self, spec: PromptSpec, nodo: str, historia: str = "", evidence_snapshot_id: str = ""
    ) -> MetadatosPrompt:
        # La huella tiene que preguntarle al MISMO chat que resolvió este nodo, no al de por
        # defecto: si no, un nodo con cadena propia reportaría el proveedor de otro.
        chat = self._chat_de(spec)
        uso = chat.ultimo_uso() if hasattr(chat, "ultimo_uso") else None
        return MetadatosPrompt(
            prompt_id=spec.id,
            prompt_version=spec.version,
            prompt_sha256=hashlib.sha256(spec.texto.encode("utf-8")).hexdigest(),
            nodo=nodo,
            historia=historia,
            model=getattr(chat, "descripcion", self._modelo_desc) or self._modelo_desc,
            provider_used=uso.proveedor if uso else "",
            model_used=uso.modelo if uso else "",
            attempt=uso.intento if uso else None,
            temperature=self._temperature,
            catalog_sha256=self._catalog_sha256,
            evidence_snapshot_id=evidence_snapshot_id,
        )

    # ── nodo 1 ───────────────────────────────────────────────────────────────
    def extraer_intencion(
        self, historia: HistoriaUsuario, funcionalidad: FuncionalidadMacro
    ) -> IntencionHistoriaLLM:
        out: IntencionHistoriaLLM = self._cadena(SPEC_INTENCION, IntencionHistoriaLLM).invoke({
            "funcionalidad_macro": funcionalidad.funcionalidad_macro,
            "funcionalidad_detalle": funcionalidad.detalle or "(sin detalle adicional)",
            "historia_archivo": historia.archivo,
            "historia_titulo": historia.titulo,
            "historia_contenido": historia.contenido,
        })
        return out.model_copy(update={"metadatos": self._huella(SPEC_INTENCION, "extraer_intencion", historia.archivo)})

    # ── nodo 2a ──────────────────────────────────────────────────────────────
    def enrutar_dominios(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        intencion: IntencionHistoriaLLM,
        catalogo: list[EntradaCatalogo],
    ) -> EnrutamientoDominiosLLM:
        """Etapa 1 del routing jerárquico: 36 vías con la documentación COMPLETA de cada nodo.

        No tiene escalones porque no los necesita: la taxonomía entera son ~3.3k tokens, un orden
        de magnitud por debajo del catálogo. Si esto no cupiera, nada cabría.
        """
        areas = {e.business_area for e in catalogo if e.business_area}
        dominios = {(e.business_area, e.business_domain) for e in catalogo if e.business_domain}
        out: EnrutamientoDominiosLLM = self._cadena(
            SPEC_ENRUTAMIENTO, EnrutamientoDominiosLLM
        ).invoke({
            "funcionalidad_macro": funcionalidad.funcionalidad_macro,
            "historia_archivo": historia.archivo,
            "historia_titulo": historia.titulo,
            "historia_contenido": historia.contenido,
            "intencion_resumen": intencion.resumen_funcional or "(sin resumen)",
            "intencion_actions": _lista(intencion.business_actions),
            "intencion_objects": _lista(intencion.business_objects),
            "intencion_outcomes": _lista(intencion.outcomes),
            "intencion_dependencies": _lista(intencion.external_dependencies),
            "total_areas": len(areas),
            "total_dominios": len(dominios),
            "taxonomia_bian": formatear_taxonomia(catalogo),
        })
        return out.model_copy(update={
            "metadatos": self._huella(SPEC_ENRUTAMIENTO, "enrutar_dominios", historia.archivo)
        })

    # ── nodo 2b ──────────────────────────────────────────────────────────────
    def generar_candidatos(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        intencion: IntencionHistoriaLLM,
        catalogo: list[EntradaCatalogo],
        *,
        texto_completo: bool = False,
        totales_por_dominio: dict[str, int] | None = None,
        propietarios_bom=None,
        grupo: str | None = None,
    ) -> CandidatosHistoriaLLM:
        taxonomia = formatear_taxonomia(catalogo, totales_por_dominio)
        # Cuatro variantes del mismo prompt_id, elegidas por lo que viaja: 1.1.0 (catálogo
        # entero, byte a byte el de siempre), 1.2.0 (+<propietarios_bom>), 1.3.0 (UN grupo del
        # fan-out: vacío es respuesta válida y lo ausente no es gap), 1.3.1 (grupo + evidencia).
        if grupo:
            spec = SPEC_CANDIDATOS_GRUPO_BOM if propietarios_bom else SPEC_CANDIDATOS_GRUPO
        else:
            spec = SPEC_CANDIDATOS_BOM if propietarios_bom else SPEC_CANDIDATOS
        bloque_bom = (
            {
                "propietarios_bom": formatear_propietarios_bom(propietarios_bom),
                "propietarios_bom_total": len(propietarios_bom),
            }
            if propietarios_bom
            else {}
        )
        if grupo:
            bloque_bom["grupo_nombre"] = grupo
        out: CandidatosHistoriaLLM = self._invocar_reduciendo(
            spec,
            CandidatosHistoriaLLM,
            lambda presupuesto: {
                **bloque_bom,
                "funcionalidad_macro": funcionalidad.funcionalidad_macro,
                "historia_archivo": historia.archivo,
                "historia_titulo": historia.titulo,
                "historia_contenido": historia.contenido,
                "intencion_resumen": intencion.resumen_funcional or "(sin resumen)",
                "intencion_actions": _lista(intencion.business_actions),
                "intencion_objects": _lista(intencion.business_objects),
                "intencion_outcomes": _lista(intencion.outcomes),
                "intencion_dependencies": _lista(intencion.external_dependencies),
                "catalogo_total": len(catalogo),
                "catalogo": formatear_catalogo(catalogo, presupuesto[1], presupuesto[0]),
                # Fuera del lambda de escalones a propósito: la taxonomía es fija y pequeña, no
                # es lo que hace que una petición no quepa. Con routing solo trae los dominios
                # elegidos, porque `catalogo` ya viene acotado a ellos.
                "taxonomia_bian": taxonomia,
            },
            self._escalones_catalogo(texto_completo=texto_completo),
        )
        return out.model_copy(update={"metadatos": self._huella(spec, "generar_candidatos", historia.archivo)})

    # ── nodo 3 ───────────────────────────────────────────────────────────────
    def revisar_completitud(
        self,
        historia: HistoriaUsuario,
        intencion: IntencionHistoriaLLM,
        candidatos: CandidatosHistoriaLLM,
        catalogo: list[EntradaCatalogo],
        disponibilidad_evidencia: dict[str, str],
    ) -> RevisionCompletitudLLM:
        actuales = "\n".join(
            f'- "{c.service_domain}"  ({_lista(c.supporting_intent, "sin señal")})'
            for c in candidatos.candidatos
        ) or "(lista vacía)"
        disp = "\n".join(f'- "{sd}": {estado}' for sd, estado in sorted(disponibilidad_evidencia.items())) or "(sin datos)"
        out: RevisionCompletitudLLM = self._cadena(SPEC_COMPLETITUD, RevisionCompletitudLLM).invoke({
            "historia_archivo": historia.archivo,
            "historia_titulo": historia.titulo,
            "historia_contenido": historia.contenido,
            "intencion_actions": _lista(intencion.business_actions),
            "intencion_objects": _lista(intencion.business_objects),
            "intencion_dependencies": _lista(intencion.external_dependencies),
            "candidatos_actuales": actuales,
            "disponibilidad_evidencia": disp,
            "catalogo_total": len(catalogo),
            "indice_global": _formatear_indice_global(
                catalogo, chars_negocio=self._cag_chars_por_sd
            ),
        })
        return out.model_copy(update={"metadatos": self._huella(SPEC_COMPLETITUD, "revisar_completitud", historia.archivo)})

    # ── nodo 4 ───────────────────────────────────────────────────────────────
    def evaluar_candidato(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        intencion: IntencionHistoriaLLM,
        paquete: PaqueteEvidenciaCandidato,
    ) -> EvaluacionCandidatoLLM:
        ev = paquete.evidencia
        out: EvaluacionCandidatoLLM = self._cadena(SPEC_EVALUACION, EvaluacionCandidatoLLM).invoke({
            "funcionalidad_macro": funcionalidad.funcionalidad_macro,
            "historia_archivo": historia.archivo,
            "historia_titulo": historia.titulo,
            "historia_contenido": historia.contenido,
            "intencion_actions": _lista(intencion.business_actions),
            "intencion_objects": _lista(intencion.business_objects),
            "intencion_trace": _lista(intencion.traceability_ids),
            "candidato_origen": paquete.origen,
            "candidato_sd": paquete.service_domain,
            "candidato_area": paquete.business_area or "(sin dato)",
            "candidato_domain": paquete.business_domain or "(sin dato)",
            "candidato_patron": paquete.functional_pattern or "(sin dato)",
            "candidato_service_role": _recortar(
                paquete.service_role or "(sin Service Role en la evidencia)",
                _ROL_REVISION_MAX_CHARS,
            ),
            "candidato_crs": _lista(paquete.control_records),
            "candidato_bqs": _lista(paquete.behavior_qualifiers),
            "candidato_operaciones": _formatear_operaciones(paquete.operations),
            "candidato_schemas_bom": formatear_schemas_bom(
                paquete.schemas_detalle, priorizar=_schemas_de_operaciones(paquete.operations)
            ),
            "candidato_bom_puml": formatear_bom_puml(paquete.bom_modelo),
            "candidato_ev_estado": ev.estado,
            "candidato_ev_url": ev.source_url or "(n/d)",
            "candidato_ev_commit": ev.source_commit_sha or "(n/d)",
            "candidato_ev_sha": ev.content_sha256 or "(n/d)",
        })
        # Blindaje: la evaluación es de ESTE candidato, pase lo que pase el eco del modelo.
        return out.model_copy(update={
            "service_domain": paquete.service_domain,
            "metadatos": self._huella(
                SPEC_EVALUACION, "evaluar_candidato", historia.archivo, ev.content_sha256
            ),
        })

    # ── nodo 5 ───────────────────────────────────────────────────────────────
    def revisar_adversarial(
        self,
        historia: HistoriaUsuario,
        intencion: IntencionHistoriaLLM,
        grupos: ServiceDomainsDeHistoria,
    ) -> RevisionAdversarialLLM:
        filas = []
        for etiqueta, grupo in (
            ("DIRECTO", grupos.candidatos_directos),
            ("TENTATIVO", grupos.candidatos_tentativos),
            ("DESCARTADO", grupos.candidatos_descartados),
        ):
            for a in grupo:
                filas.append(
                    f'- "{a.service_domain}"  grupo={etiqueta}  rol={a.rol_contractual}  '
                    f"decision={a.decision_contractual}  accion_objeto={a.accion_objeto or '(vacío)'}  "
                    f"service_role={_recortar(a.rol_bian or '', _ROL_REVISION_MAX_CHARS)}"
                )
        out: RevisionAdversarialLLM = self._cadena(SPEC_ADVERSARIAL, RevisionAdversarialLLM).invoke({
            "historia_archivo": historia.archivo,
            "historia_titulo": historia.titulo,
            "historia_contenido": historia.contenido,
            "intencion_actions": _lista(intencion.business_actions),
            "intencion_objects": _lista(intencion.business_objects),
            "intencion_outcomes": _lista(intencion.outcomes),
            "clasificacion_actual": "\n".join(filas) or "(sin candidatos clasificados)",
        })
        return out.model_copy(update={"metadatos": self._huella(SPEC_ADVERSARIAL, "revisar_adversarial", historia.archivo)})

    # ── nodo 7 ───────────────────────────────────────────────────────────────
    def reconciliar_funcionalidad(
        self, funcionalidad: FuncionalidadMacro, resumen_por_historia: list[dict]
    ) -> ReconciliacionFuncionalidadLLM:
        bloques = []
        for h in resumen_por_historia:
            lineas = [f'HU {h.get("archivo", "?")} — {h.get("titulo", "")}']
            for sd in h.get("service_domains", []):
                lineas.append(
                    f'  - "{sd.get("service_domain")}"  grupo={sd.get("grupo")}  rol={sd.get("rol_contractual")}  '
                    f'decision={sd.get("decision_contractual")}  ownership={_lista(sd.get("ownership_traceability", []))}  '
                    f'dependency={_lista(sd.get("dependency_traceability", []))}'
                )
            bloques.append("\n".join(lineas))
        out: ReconciliacionFuncionalidadLLM = self._cadena(
            SPEC_RECONCILIACION, ReconciliacionFuncionalidadLLM
        ).invoke({
            "funcionalidad_macro": funcionalidad.funcionalidad_macro,
            "funcionalidad_detalle": funcionalidad.detalle or "(sin detalle adicional)",
            "historias_clasificadas": "\n\n".join(bloques) or "(sin historias)",
        })
        return out.model_copy(update={"metadatos": self._huella(SPEC_RECONCILIACION, "reconciliar_funcionalidad")})
