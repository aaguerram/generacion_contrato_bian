"""Regla de dominio: ancla los Service Domains propuestos por el LLM a la evidencia local y
los reparte en dos ejes: aplicabilidad semantica (grupo) y decision contractual (motivo).

Pasos deterministas (stdlib + pydantic + dominio, sin frameworks, sin API):

1. **Resolución** de cada nombre propuesto contra el catálogo BIAN R14 (Service Landscape, 341 SD):
   - match normalizado exacto            -> MATCH   (nombre canónico del catálogo)
   - si no, subcadena normalizada única  -> MATCH   (se recupera el nombre canónico)
   - varias coincidencias                -> AMBIGUOUS  (se descarta, se registra el motivo)
   - ninguna                             -> NOT_FOUND  (se descarta)
2. **Anclaje**: nombre canónico + Service Role + Functional Pattern + Business Area/Domain
   se copian DESDE el catálogo, nunca del LLM.
3. **Score determinista** (`scoring_bian`): correspondencia con la evidencia oficial (Service
   Role, operaciones, schemas), rúbrica estructurada 0-3, ownership, trazabilidad y jerarquía.
   La confianza libre del LLM NO entra en el score (solo se conserva como `confianza_llm`).
4. **Tope por rol contractual**: un SD cuyo `rol_contractual` no es `OWNED_CONTRACT`
   **nunca** cae en `candidatos_directos`.
5. **Dos ejes de decisión**:
   - grupo (aplicabilidad): `directo` (>= umbral_directo) / `tentativo` / `descartado`.
   - decision_contractual: `SELECTED` / `UNRESOLVED` / `REJECTED` + `motivo_decision`.
     Evidencia BOM ausente NO degrada a rechazo semántico salvo que el score ya sea de por sí
     `descartado` (score < umbral_tentativo): entonces es `OUT_OF_SCOPE`. Si el score alcanza la
     banda tentativa pero falta evidencia -> `UNRESOLVED / NO_OFFICIAL_BIAN_EVIDENCE`.
6. **Dedup** por SD (se queda con la mayor confianza cruda) y orden por confianza desc.
7. **Promoción de ownership** (`determinar_promociones` / `propuestos_promovidos`): el revisor
   adversarial puede señalar que una acción directa de la historia quedó mal clasificada como
   `CONSUMED_DEPENDENCY`. El código nunca confía en esa sola señal: solo promueve a
   `OWNED_CONTRACT` cuando, ADEMÁS, `dependency_kind` es del tipo que significa "este SD es el
   resultado/salida que la historia produce" (no una precondición), hay trazabilidad de
   escenarios, evidencia de operación oficial citada, y correspondencia léxica real con el objeto
   de negocio (`objeto_bom`), y el propio revisor no contradijo el Service Role para el mismo SD.
8. **Degradación de ownership** (`determinar_degradaciones` / `propuestos_degradados`), simétrica
   en sentido contrario: el revisor puede señalar que un SD evaluado `OWNED_CONTRACT` en realidad
   solo se consulta como precondición. El código tampoco confía en esa sola señal: solo degrada a
   `CONSUMED_DEPENDENCY` cuando, ADEMÁS, la acción que el candidato cita no tiene NINGÚN token en
   común con las `business_actions` que la propia historia declaró en `extraer_intencion` (antes
   de proponer ningún SD) — confirmación independiente equivalente a `objeto_bom` en la promoción.
   Ninguna de las dos direcciones la decide el LLM solo por su cuenta: ambas son reglas
   deterministas sobre lo que el LLM reportó, verificadas contra una señal calculada por separado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.dominio.historias import (
    DependencyKind,
    DesgloseScore,
    EvidenciaBian,
    IntencionHistoriaLLM,
    RevisionAdversarialLLM,
    ServiceDomainAsignado,
    ServiceDomainPropuestoLLM,
    ServiceDomainsDeHistoria,
)
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar
from src.dominio.scoring_bian import _sim, _split_camel, calcular_score
from src.dominio.vocabulario_bian import EQUIVALENCIAS_RETRIEVAL

_EPS = 0.001  # margen para dejar un SD topado justo por debajo del umbral directo


@dataclass(frozen=True)
class UmbralesMapeo:
    directo: float = 0.90  # confianza >= directo  -> candidato directo
    tentativo: float = 0.63  # tentativo <= confianza < directo -> tentativo; menos -> descartado

    def __post_init__(self) -> None:
        if not (0.0 <= self.tentativo <= self.directo <= 1.0):
            raise ValueError(
                f"Umbrales de mapeo inválidos: tentativo={self.tentativo}, directo={self.directo}"
            )

    def grupo_de(self, confianza: float) -> str:
        if confianza >= self.directo:
            return "directo"
        if confianza >= self.tentativo:
            return "tentativo"
        return "descartado"


def resolver_nombre_sd(
    nombre: str, indice: dict[str, EntradaCatalogo]
) -> tuple[EntradaCatalogo | None, str]:
    """Resuelve `nombre` contra el índice normalizado del catálogo. Devuelve (entrada, resolución)."""
    clave = normalizar(nombre)
    if not clave:
        return None, "NOT_FOUND"
    exacto = indice.get(clave)
    if exacto is not None:
        return exacto, "MATCH"
    contiene = [
        entrada for k, entrada in indice.items() if len(clave) >= 4 and (clave in k or k in clave)
    ]
    if len(contiene) == 1:
        return contiene[0], "MATCH"
    if len(contiene) > 1:
        return None, "AMBIGUOUS"
    return None, "NOT_FOUND"


def _decidir(
    *,
    es_owned: bool,
    rol_contractual: str,
    grupo: str,
    scoring_activo: bool,
    evidencia_faltante: bool,
) -> tuple[str, str]:
    """(decision_contractual, motivo_decision) a partir de los dos ejes. Determinista."""
    if not es_owned:
        # una dependencia consumida / relación temática NUNCA genera contrato: contractualmente
        # es REJECTED. El grupo/score sigue reflejando lo requerida que está la dependencia.
        motivo = (
            "CONSUMED_DEPENDENCY"
            if rol_contractual == "CONSUMED_DEPENDENCY"
            else "RELATED_NOT_OWNED"
        )
        return "REJECTED", motivo

    if grupo == "descartado":
        # score por debajo de la banda tentativa: no aplica, aunque falte evidencia oficial
        return "REJECTED", "OUT_OF_SCOPE"

    if scoring_activo and evidencia_faltante:
        # score suficiente pero sin BOM oficial verificable -> nunca "no aplica"
        return "UNRESOLVED", "NO_OFFICIAL_BIAN_EVIDENCE"

    if grupo == "directo":
        return "SELECTED", "OWNED_SELECTED"

    return "UNRESOLVED", "TENTATIVE_SCORE"


def clasificar_service_domains(
    propuestos: list[ServiceDomainPropuestoLLM],
    catalogo: list[EntradaCatalogo],
    umbrales: UmbralesMapeo,
    *,
    operaciones_por_sd: dict[str, list] | None = None,
    evidencias_por_sd: dict | None = None,
    esquemas_por_sd: dict[str, list[str]] | None = None,
    origen_por_sd: dict[str, str] | None = None,
) -> ServiceDomainsDeHistoria:
    """Convierte la lista cruda del LLM en los 3 grupos, anclando cada SD a la evidencia local."""
    indice = {normalizar(e.service_domain): e for e in catalogo}

    mejor: dict[str, tuple[ServiceDomainPropuestoLLM, EntradaCatalogo]] = {}
    for p in propuestos:
        entrada, resolucion = resolver_nombre_sd(p.service_domain, indice)
        if entrada is None or resolucion != "MATCH":
            continue  # AMBIGUOUS / NOT_FOUND -> fuera (anti-alucinación)
        clave = entrada.service_domain
        confianza_llm = max(0.0, min(1.0, float(p.confianza)))
        actual = mejor.get(clave)
        if actual is None or confianza_llm > float(actual[0].confianza):
            mejor[clave] = (p.model_copy(update={"confianza": confianza_llm}), entrada)

    scoring_activo = evidencias_por_sd is not None
    tope_no_owned = max(0.0, umbrales.directo - _EPS)
    asignados: list[ServiceDomainAsignado] = []
    for clave, (p, entrada) in mejor.items():
        confianza_llm = float(p.confianza)
        es_owned = p.rol_contractual == "OWNED_CONTRACT"
        evidencia = (evidencias_por_sd or {}).get(clave)
        operaciones = (operaciones_por_sd or {}).get(clave, [])
        esquemas = (esquemas_por_sd or {}).get(clave, [])

        if evidencia is not None:
            desglose, observaciones = calcular_score(p, entrada, operaciones, evidencia, esquemas)
            confianza = desglose.total
        else:
            desglose, observaciones = DesgloseScore(total=confianza_llm), []
            evidencia = EvidenciaBian()
            confianza = confianza_llm

        evidencia_faltante = scoring_activo and evidencia.estado == "BIAN_EVIDENCE_UNAVAILABLE"
        confianza = confianza if es_owned else min(confianza, tope_no_owned)
        if evidencia_faltante:
            confianza = min(confianza, tope_no_owned)

        grupo = umbrales.grupo_de(confianza)
        decision, motivo = _decidir(
            es_owned=es_owned,
            rol_contractual=p.rol_contractual,
            grupo=grupo,
            scoring_activo=scoring_activo,
            evidencia_faltante=evidencia_faltante,
        )

        asignados.append(
            ServiceDomainAsignado(
                service_domain=entrada.service_domain,
                resolucion="MATCH",
                rol_contractual=p.rol_contractual,
                dependency_kind=p.dependency_kind if not es_owned else None,
                confianza=round(confianza, 4),
                confianza_pct=round(confianza * 100),
                confianza_llm=round(confianza_llm, 4),
                grupo=grupo,  # type: ignore[arg-type]
                accion_objeto=p.accion_objeto.strip(),
                escenarios_hu=[s.strip() for s in p.escenarios_hu if s and s.strip()],
                justificacion=p.justificacion.strip(),
                business_area=entrada.business_area,
                business_domain=entrada.business_domain,
                rol_bian=entrada.service_role,
                patron_funcional=entrada.functional_pattern,
                origen_candidato=(origen_por_sd or {}).get(clave, "llm"),  # type: ignore[arg-type]
                evidencia_bian=evidencia,
                desglose_score=desglose.model_copy(update={"total": round(confianza, 4)}),
                decision_contractual=decision,  # type: ignore[arg-type]
                motivo_decision=motivo,  # type: ignore[arg-type]
                ambiguity=p.ambiguity,
                observaciones_adversariales=observaciones,
                ownership_traceability=[
                    s.strip() for s in p.ownership_traceability if s and s.strip()
                ],
                dependency_traceability=[
                    s.strip() for s in p.dependency_traceability if s and s.strip()
                ],
                evidence_refs=[s.strip() for s in p.evidence_refs if s and s.strip()],
                reason_codes=list(dict.fromkeys(p.reason_codes)),
                assumptions=list(p.assumptions),
                gaps=list(p.gaps),
                blocking_codes=list(dict.fromkeys(p.blocking_codes)),
            )
        )

    def _orden(x: ServiceDomainAsignado) -> tuple[float, str]:
        return (-x.confianza, x.service_domain.lower())

    return ServiceDomainsDeHistoria(
        candidatos_directos=sorted((a for a in asignados if a.grupo == "directo"), key=_orden),
        candidatos_tentativos=sorted((a for a in asignados if a.grupo == "tentativo"), key=_orden),
        candidatos_descartados=sorted(
            (a for a in asignados if a.grupo == "descartado"), key=_orden
        ),
    )


# Hallazgos adversariales que degradan una decisión (el LLM nunca promueve, solo el código decide).
# NOTA: "ACCION_DIRECTA_COMO_DEPENDENCIA" NO degrada -> significa lo opuesto (una acción directa
# quedó como dependencia) y solo puede PROMOVER, nunca degradar; ver `determinar_promociones`.
_DEGRADA_SELECTED = {
    "DEPENDENCIA_PROMOVIDA_A_CONTRATO": "BIAN-SCOPE-002",
    "DIRECTO_SIN_SERVICE_ROLE": "BIAN-SCOPE-003",
}

# `dependency_kind` que puede indicar que el SD produce el RESULTADO que la historia ejecuta
# (p.ej. una notificación es la salida directa), en vez de ser una precondición consultada antes
# de actuar (SECURITY_GUARD/SUPPORTING_LOOKUP/EXTERNAL_PROVIDER/RISK_INPUT). Solo estos tipos son
# elegibles para promoción — no cualquier `CONSUMED_DEPENDENCY` con un hallazgo adversarial.
_PROMOCION_DEPENDENCY_KINDS: frozenset[DependencyKind] = frozenset({"AUDIT_OR_NOTIFICATION"})

# Piso de `desglose_score.objeto_bom` para promover/finalizar por evidencia sin score directo (ver
# `determinar_promociones` / `finalizar_por_operacion_solida`). Filtra el caso real observado:
# "Party Authentication" citó su propio CR (`PartyAuthenticationAssessment`) como `evidence_refs`
# para una historia de "enviar notificación" -evidencia real pero de un objeto de negocio distinto,
# objeto_bom=0.0 exacto- y sin este piso quedaba promovido/finalizado igual. 0.15 es
# deliberadamente bajo (Correspondence real dio 0.3333; los casos de prueba scriptados dan 1.0):
# solo bloquea el caso de correlación CERO, no exige un match fuerte.
OBJETO_BOM_MINIMO_PROMOCION = 0.15

PROMOTED_REASON_CODE = "OWNERSHIP_PROMOTED_BY_ADVERSARIAL"


def determinar_promociones(
    grupos: ServiceDomainsDeHistoria,
    revision: RevisionAdversarialLLM,
    *,
    objeto_bom_minimo: float = OBJETO_BOM_MINIMO_PROMOCION,
) -> frozenset[str]:
    """Nombres normalizados de SD que pasan de `CONSUMED_DEPENDENCY` a `OWNED_CONTRACT`.

    Exige TODO lo siguiente (genérico, sin nombrar ningún Service Domain):
    - un hallazgo `ACCION_DIRECTA_COMO_DEPENDENCIA` para ese SD, Y ningún `DIRECTO_SIN_SERVICE_ROLE`
      para el mismo SD (el propio revisor no contradice el Service Role);
    - `rol_contractual == CONSUMED_DEPENDENCY` con `dependency_kind` en `_PROMOCION_DEPENDENCY_KINDS`
      (el SD es la salida/resultado que la historia produce, no una precondición consultada);
    - trazabilidad a escenarios (`dependency_traceability`) y al menos una cita de evidencia
      (`evidence_refs`, típicamente una operación oficial) — sin esto, no hay base determinista;
    - `desglose_score.objeto_bom >= objeto_bom_minimo`: el LLM (evaluación + revisor adversarial)
      puede citar `evidence_refs` no vacío señalando CUALQUIER operación real del SD -incluido el
      nombre del propio Control Record, que `operacion_evidencia_verificable` acepta como cita
      válida por diseño- sin que esa operación tenga relación real con el objeto de negocio de la
      historia (caso real: "Party Authentication" fue promovido citando su propio CR
      `PartyAuthenticationAssessment` para una historia de "enviar notificación" — evidencia
      "real" pero irrelevante). `objeto_bom` es la única componente del score que mide
      específicamente esa correspondencia con evidencia léxica (no solo autoreporte del LLM); un
      valor de 0 significa que ni el texto de las operaciones/BOM del SD ni la rúbrica
      `match_objeto_negocio` encontraron NADA en común con lo que la historia administra.
    """
    hallazgos_por_sd: dict[str, list[str]] = {}
    for h in revision.hallazgos:
        if h.service_domain:
            hallazgos_por_sd.setdefault(normalizar(h.service_domain), []).append(h.tipo)

    todos = {
        normalizar(a.service_domain): a
        for a in (
            *grupos.candidatos_directos,
            *grupos.candidatos_tentativos,
            *grupos.candidatos_descartados,
        )
    }

    promovidos: set[str] = set()
    for clave, tipos in hallazgos_por_sd.items():
        if "ACCION_DIRECTA_COMO_DEPENDENCIA" not in tipos or "DIRECTO_SIN_SERVICE_ROLE" in tipos:
            continue
        a = todos.get(clave)
        if (
            a is not None
            and a.rol_contractual == "CONSUMED_DEPENDENCY"
            and a.dependency_kind in _PROMOCION_DEPENDENCY_KINDS
            and a.dependency_traceability
            and a.evidence_refs
            and a.desglose_score.objeto_bom >= objeto_bom_minimo
        ):
            promovidos.add(clave)
    return frozenset(promovidos)


def propuestos_promovidos(
    propuestos_por_sd: dict[str, ServiceDomainPropuestoLLM], promovidos: frozenset[str]
) -> dict[str, ServiceDomainPropuestoLLM]:
    """Copia `propuestos_por_sd` con los SD de `promovidos` reescritos a `OWNED_CONTRACT`.

    La trazabilidad que el LLM etiquetó como "consumo" pasa a ser trazabilidad de ownership: ya
    está probado (por la regla de `determinar_promociones`) que es responsabilidad directa, no
    una precondición. El llamador debe recalcular score/decisión con `clasificar_service_domains`
    sobre el resultado — este helper solo reescribe la entrada, nunca el score.
    """
    salida = dict(propuestos_por_sd)
    for clave in promovidos:
        p = salida.get(clave)
        if p is None:
            continue
        salida[clave] = p.model_copy(
            update={
                "rol_contractual": "OWNED_CONTRACT",
                "dependency_kind": None,
                "ownership_traceability": list(
                    dict.fromkeys([*p.ownership_traceability, *p.dependency_traceability])
                ),
                "dependency_traceability": [],
            }
        )
    return salida


DEMOTED_REASON_CODE = "OWNERSHIP_DEMOTED_BY_ADVERSARIAL"


def determinar_degradaciones(
    grupos: ServiceDomainsDeHistoria,
    intencion: IntencionHistoriaLLM,
    revision: RevisionAdversarialLLM,
) -> frozenset[str]:
    """Nombres normalizados de SD que pasan de `OWNED_CONTRACT` a `CONSUMED_DEPENDENCY`.

    Simétrico a `determinar_promociones`, en la dirección contraria. Caso real que lo motivó:
    "Party Reference Data Directory" fue evaluado `OWNED_CONTRACT` (accion_objeto="actualizar
    número de celular o correo electrónico") para la historia "Notificar actualización de datos"
    -que solo NOTIFICA, la actualización es una precondición ya ocurrida ("cuando el usuario
    actualiza...")-. El revisor adversarial señaló `DEPENDENCIA_PROMOVIDA_A_CONTRATO`, y
    `aplicar_hallazgos_adversariales` YA degradaba `SELECTED`->`UNRESOLVED` para ese hallazgo, pero
    solo bloqueaba para revisión humana en vez de reclasificar.

    Exige, además del hallazgo:
    - `rol_contractual == OWNED_CONTRACT` (el eje que está en disputa);
    - el `accion_objeto` que el candidato cita NO tiene NINGÚN token en común con
      `intencion.business_actions` — las acciones que la propia historia declaró en
      `extraer_intencion`, ANTES de que se propusiera ningún Service Domain. Es la confirmación
      independiente equivalente a `objeto_bom` en la promoción: no basta con que el revisor
      adversarial lo señale (podría estar equivocado, igual que la evaluación original), hace
      falta que el código verifique que la acción citada no es ninguna de las que la historia
      misma dice ejecutar. Si `intencion.business_actions` viene vacío no hay con qué confirmar
      nada -> no degrada (se queda en el `UNRESOLVED` bloqueado, conservador por defecto).

    A diferencia de la promoción, NO exige ausencia de un hallazgo contrario
    (`DIRECTO_SIN_SERVICE_ROLE` para el mismo SD apunta en la MISMA dirección aquí — el rol no
    encaja —, no la contradice).
    """
    if not intencion.business_actions:
        return frozenset()
    acciones_historia = " ".join(intencion.business_actions)

    hallazgos_por_sd: dict[str, list[str]] = {}
    for h in revision.hallazgos:
        if h.service_domain:
            hallazgos_por_sd.setdefault(normalizar(h.service_domain), []).append(h.tipo)

    todos = {
        normalizar(a.service_domain): a
        for a in (
            *grupos.candidatos_directos,
            *grupos.candidatos_tentativos,
            *grupos.candidatos_descartados,
        )
    }

    degradados: set[str] = set()
    for clave, tipos in hallazgos_por_sd.items():
        if "DEPENDENCIA_PROMOVIDA_A_CONTRATO" not in tipos:
            continue
        a = todos.get(clave)
        if (
            a is not None
            and a.rol_contractual == "OWNED_CONTRACT"
            and _sim(a.accion_objeto, acciones_historia) == 0.0
        ):
            degradados.add(clave)
    return frozenset(degradados)


def propuestos_degradados(
    propuestos_por_sd: dict[str, ServiceDomainPropuestoLLM], degradados: frozenset[str]
) -> dict[str, ServiceDomainPropuestoLLM]:
    """Copia `propuestos_por_sd` con los SD de `degradados` reescritos a `CONSUMED_DEPENDENCY`.

    Simétrico a `propuestos_promovidos`. `dependency_kind=SUPPORTING_LOOKUP` (precondición
    consultada antes de actuar) porque lo único que `determinar_degradaciones` probó es que NO es
    ownership — no de qué tipo específico de dependencia se trata; es el género más genérico de
    los no-promocionables. El llamador debe recalcular score/decisión con
    `clasificar_service_domains`: una vez `rol_contractual != OWNED_CONTRACT`, `_decidir` ya
    garantiza `REJECTED`/`CONSUMED_DEPENDENCY` sin importar el score (no hace falta finalizar nada
    a mano, a diferencia de la promoción)."""
    salida = dict(propuestos_por_sd)
    for clave in degradados:
        p = salida.get(clave)
        if p is None:
            continue
        salida[clave] = p.model_copy(
            update={
                "rol_contractual": "CONSUMED_DEPENDENCY",
                "dependency_kind": "SUPPORTING_LOOKUP",
                "dependency_traceability": list(
                    dict.fromkeys([*p.dependency_traceability, *p.ownership_traceability])
                ),
                "ownership_traceability": [],
            }
        )
    return salida


def _tokens_comparables(texto: str) -> set[str]:
    """Tokens normalizados y traducidos al inglés, para cruzar catálogo con texto del LLM.

    No reusa `scoring_bian._tokens` a propósito: aquel usa el mapa BASE, que es el que fija el
    score y tiene su propia regresión. Aquí hace falta el mapa de recuperación, más amplio
    (`contacto -> contact`, que BASE no trae), y tocar el del scoring para conseguirlo movería
    números que no tienen nada que ver con esta comprobación.
    """
    plano = (
        unicodedata.normalize("NFKD", _split_camel(texto or "").lower())
        .encode("ascii", "ignore")
        .decode()
    )
    return {
        EQUIVALENCIAS_RETRIEVAL.get(t, t)
        for t in re.findall(r"[a-z0-9]+", plano)
        if len(t) > 2
    }


def _tokens_en_comun(nombre_objeto: str, objeto_en_disputa: str) -> set[str]:
    """Términos compartidos entre el nodo del catálogo y el objeto que el conflicto disputa.

    Además de la intersección exacta, acepta **variantes morfológicas de la misma raíz**: el
    catálogo escribe `Notification Record` y el LLM escribe "enviar notificación", que el
    vocabulario traduce a `notify` — misma raíz, palabras distintas. Sin esto la condición sería
    tan estricta que no confirmaría nunca. Se exige raíz de 5 caracteres para que la coincidencia
    siga siendo explicable: `notif|icación` sí, `pay|ment` contra `pay|ee` no.
    """
    izquierda, derecha = _tokens_comparables(nombre_objeto), _tokens_comparables(objeto_en_disputa)
    comunes = izquierda & derecha
    for x in izquierda - comunes:
        for y in derecha - comunes:
            if len(x) >= 5 and len(y) >= 5 and (x.startswith(y[:5]) or y.startswith(x[:5])):
                comunes.add(x)
    return comunes


CONFLICTO_CONFIRMADO_POR_GRAFO = "OWNERSHIP_CONFLICT_CONFIRMED_BY_GRAPH"
CONFLICTO_SIN_RESPALDO_DE_GRAFO = "OWNERSHIP_CONFLICT_NOT_BACKED_BY_GRAPH"


def confirmar_conflictos_por_grafo(
    objeto_en_disputa_por_sd: dict[str, str],
    objetos_compartidos: list,
) -> dict[str, tuple[str, str]]:
    """¿El catálogo BIAN respalda el conflicto de ownership que afirmó el revisor adversarial?

    Un `ownership_conflict` dice "estos Service Domains reclaman el mismo objeto de negocio".
    Hasta ahora eso era **solo la opinión del LLM**: quedaba como incidencia
    `OWNERSHIP_CONFLICT_UNRESOLVED` sin nada que la confirmara o la desmintiera. El grafo canónico
    sí puede comprobarlo, porque sabe qué nodos del modelo toca cada SD.

    La comprobación tiene **tres** partes, y las dos últimas son las que hacen que la señal diga
    algo:

    1. ¿Existe un nodo real (clase del BOM, schema, Control Record) que ambos toquen?
    2. ¿Ese nodo **discrimina**? Compartir `Party` no es un conflicto: la modelan 125 Service
       Domains, es el andamiaje del modelo BIAN. Solo cuenta un nodo específico
       (`ObjetoCompartido.especifico`, mismo umbral que la expansión por grafo).
    3. ¿Ese nodo tiene que ver con **el objeto en disputa**? Esta condición se añadió después de
       medirla: con 11 candidatos en una historia, la señal confirmó 6 conflictos apoyándose en
       objetos sin relación con lo disputado —`Access Arrangement` entre Correspondence y Customer
       Access Entitlement para un conflicto sobre "enviar notificación"—. Sin ella la regla
       responde "¿comparte este candidato algo específico con ALGÚN otro?", cuya probabilidad
       crece con el número de candidatos, en vez de "¿respalda el catálogo ESTE conflicto?".

    `objeto_en_disputa_por_sd` = `{service_domain: accion_objeto}`, el objeto que el propio
    pipeline ya atribuyó a ese candidato al clasificarlo. Devuelve
    `{sd_normalizado: (veredicto, detalle)}`. **No reclasifica nada**: igual que el resto del
    módulo, una señal sola no mueve una decisión — aquí decide si el conflicto queda como
    incidencia accionable o como ruido anotado. Sin grafo, el dict va vacío y todo sigue igual.
    """
    if not objeto_en_disputa_por_sd or not objetos_compartidos:
        return {}
    especificos = [o for o in objetos_compartidos if getattr(o, "especifico", False)]
    veredictos: dict[str, tuple[str, str]] = {}
    for sd, objeto_disputa in objeto_en_disputa_por_sd.items():
        clave = normalizar(sd)
        if not clave:
            continue
        tocan_al_sd = [
            o
            for o in especificos
            if any(normalizar(x) == clave for x in getattr(o, "service_domains", []))
        ]
        respaldo = [o for o in tocan_al_sd if _tokens_en_comun(o.nombre, objeto_disputa)]
        if respaldo:
            objeto = respaldo[0]
            otros = [x for x in objeto.service_domains if normalizar(x) != clave]
            comunes = sorted(_tokens_en_comun(objeto.nombre, objeto_disputa))
            veredictos[clave] = (
                CONFLICTO_CONFIRMADO_POR_GRAFO,
                f"el catálogo BIAN confirma el conflicto: '{objeto.nombre}' ({objeto.tipo}) lo "
                f"modelan también {', '.join(otros)} y solo {objeto.total_service_domains} "
                f"Service Domain(s) en total, y coincide con el objeto en disputa "
                f"('{objeto_disputa}') en: {', '.join(comunes)}.",
            )
        elif tocan_al_sd:
            veredictos[clave] = (
                CONFLICTO_SIN_RESPALDO_DE_GRAFO,
                "el catálogo BIAN no respalda el conflicto: los objetos específicos que este "
                f"Service Domain comparte con los otros candidatos ({', '.join(sorted({o.nombre for o in tocan_al_sd})[:3])}) "
                f"no tienen nada que ver con el objeto en disputa ('{objeto_disputa}').",
            )
        else:
            genericos = sorted(
                {o.nombre for o in objetos_compartidos if not getattr(o, "especifico", False)}
            )[:3]
            veredictos[clave] = (
                CONFLICTO_SIN_RESPALDO_DE_GRAFO,
                "el catálogo BIAN no respalda el conflicto: no hay ningún objeto específico "
                "compartido con los otros candidatos"
                + (
                    f"; solo genéricos ({', '.join(genericos)}), que medio catálogo modela."
                    if genericos
                    else "."
                ),
            )
    return veredictos


def candidatos_operacion_elegibles(grupos: ServiceDomainsDeHistoria) -> list[ServiceDomainAsignado]:
    """SD con base suficiente para intentar anclar operaciones oficiales: `OWNED_CONTRACT`,
    directo O tentativo. Desacopla la selección de operaciones del umbral de confianza directa
    (0.90): un SD correctamente identificado como propietario pero con confianza tentativa sigue
    teniendo una operación oficial real que documentar para revisión — no depende de que la
    historia por sí sola alcance el umbral de "directo". Los descartados no entran: ahí el score
    es demasiado bajo o el rol no es de ownership, no hay base para anclar nada. Nunca incluye
    `CONSUMED_DEPENDENCY`/`RELATED_NOT_OWNED`: eso seguiría mezclando "operación referenciada" con
    "operación contratada", que es exactamente lo que este desacople evita."""
    return [
        a
        for a in (*grupos.candidatos_directos, *grupos.candidatos_tentativos)
        if a.rol_contractual == "OWNED_CONTRACT"
    ]


OPERATION_FINALIZED_REASON_CODE = "OWNED_FINALIZED_BY_OPERATION_EVIDENCE"


def _finalizar_como_directo(
    objetivo: ServiceDomainAsignado,
    directos: list[ServiceDomainAsignado],
    tentativos: list[ServiceDomainAsignado],
    descartados: list[ServiceDomainAsignado],
) -> None:
    """Mueve `objetivo` a `directos` (mutando las tres listas in-place) y fija
    `SELECTED`/`OWNED_SELECTED`. No decide NADA por sí solo — el llamador ya verificó la evidencia
    que justifica saltarse el umbral numérico de 0.90; esto solo aplica el movimiento."""
    clave = normalizar(objetivo.service_domain)
    if objetivo.grupo != "directo":
        tentativos[:] = [a for a in tentativos if normalizar(a.service_domain) != clave]
        descartados[:] = [a for a in descartados if normalizar(a.service_domain) != clave]
        objetivo.grupo = "directo"
        directos.append(objetivo)
    objetivo.decision_contractual = "SELECTED"
    objetivo.motivo_decision = "OWNED_SELECTED"


def finalizar_por_operacion_solida(
    grupos: ServiceDomainsDeHistoria, *, objeto_bom_minimo: float = OBJETO_BOM_MINIMO_PROMOCION
) -> ServiceDomainsDeHistoria:
    """Se llama DESPUÉS de anclar operaciones (`_asignar_operaciones`). Un candidato
    `OWNED_CONTRACT` con evidencia BIAN oficial verificada Y al menos una operación anclada sin
    `OPERATION_EVIDENCE_UNVERIFIED` (la única reserva que refleja incertidumbre real sobre SI la
    cita del LLM corresponde a un campo real — `OPERATION_ID_RECONSTRUCTED_FROM_PATH` no cuenta:
    ahí la operación en sí ya quedó resuelta con certeza estructural, contra el path/method reales
    del catálogo, `resolver_operation_id`; el único caveat es el FORMATO en que el LLM la citó, no
    si es la correcta) ya reúne tres señales independientes de que la identificación es correcta:
    el LLM lo propuso como propietario, hay evidencia BIAN real, y hay una operación oficial
    concreta y verificada que la implementa. Eso pesa más que el score léxico agregado, que puede
    quedar estructuralmente bajo para Service Domains "administrativos" (Business Area/Domain sin
    vocabulario compartido con la historia, p.ej. Correspondence / "Business Support / Document
    Management and Archive" contra "notificar cambio de datos") aun cuando la identificación ya
    era correcta desde la primera evaluación (sin pasar por `determinar_promociones`). Mismo piso
    `objeto_bom_minimo` que la promoción (misma vulnerabilidad: `operacion_evidencia_verificable`
    acepta citar el propio `grupo`/`operation_id` como evidencia "verificada", lo que no garantiza
    que esa operación tenga relación real con el objeto de negocio de la historia). Recorre los TRES
    grupos, incluido `directo`: estar en el grupo `directo` (score >= 0.90) NO implica estar
    `SELECTED`, porque `aplicar_hallazgos_adversariales` degrada la DECISIÓN sin mover el
    candidato de grupo. Un propietario con evidencia sólida podía así quedarse sin contrato solo
    por estar ya en `directo` -- caso real medido: Party Reference Data Directory con confianza
    0.9650, `objeto_bom` 1.0, evidencia `CACHED_VERIFIED` y `RetrieveReference` anclada sin
    reservas, y aun así `UNRESOLVED/TENTATIVE_SCORE`. Idempotente: sobre un candidato ya
    `SELECTED` no cambia nada."""
    directos = list(grupos.candidatos_directos)
    tentativos = list(grupos.candidatos_tentativos)
    descartados = list(grupos.candidatos_descartados)
    for a in (*directos, *tentativos, *descartados):
        if a.decision_contractual == "SELECTED":
            continue
        if (
            a.rol_contractual == "OWNED_CONTRACT"
            and a.evidencia_bian.estado in ("VERIFIED", "CACHED_VERIFIED")
            and a.desglose_score.objeto_bom >= objeto_bom_minimo
            and any(
                "OPERATION_EVIDENCE_UNVERIFIED" not in o.reason_codes for o in a.operaciones_bian
            )
        ):
            a.reason_codes = list(dict.fromkeys([*a.reason_codes, OPERATION_FINALIZED_REASON_CODE]))
            _finalizar_como_directo(a, directos, tentativos, descartados)

    def _orden(a: ServiceDomainAsignado) -> tuple[float, str]:
        return (-a.confianza, a.service_domain.lower())

    return ServiceDomainsDeHistoria(
        candidatos_directos=sorted(directos, key=_orden),
        candidatos_tentativos=sorted(tentativos, key=_orden),
        candidatos_descartados=sorted(descartados, key=_orden),
    )


NO_OPERATION_REASON_CODE = "DOWNGRADED_NO_OPERATION_ANCHORED"


def degradar_sin_operacion_anclada(
    grupos: ServiceDomainsDeHistoria, service_domains_con_operaciones: set[str]
) -> ServiceDomainsDeHistoria:
    """Se llama DESPUÉS de anclar operaciones y de `finalizar_por_operacion_solida`. Un candidato
    `SELECTED` que no logró anclar NINGUNA de las operaciones oficiales de su Service Domain no
    puede presentarse como contrato resuelto: el entregable de este pipeline es "qué operación
    BIAN implementa esta historia", y sin operación no hay nada que implementar.

    Es el movimiento simétrico de `finalizar_por_operacion_solida`: aquella sube a `SELECTED` con
    evidencia de operación sólida; esta baja a `UNRESOLVED` cuando esa evidencia falta del todo.
    Y como el resto del módulo, exige una señal calculada aparte antes de mover nada: solo aplica
    si el Service Domain SÍ tenía operaciones oficiales en el catálogo
    (`service_domains_con_operaciones`). Si el catálogo no trae ninguna, o el paso de operaciones
    está apagado (`--sin-operaciones`), no hay nada que reprochar y no se toca.

    Caso real que lo motivó: en 2 de 3 corridas, `Party Reference Data Directory` salía `SELECTED`
    junto a Correspondence -promovido por el revisor adversarial- con sus 17 operaciones oficiales
    disponibles y NINGUNA anclada. No se mueve de grupo, solo cambia la decisión: el mismo
    tratamiento que ya aplica la degradación adversarial.
    """
    if not service_domains_con_operaciones:
        return grupos
    disponibles = {normalizar(sd) for sd in service_domains_con_operaciones}
    for a in (*grupos.candidatos_directos, *grupos.candidatos_tentativos):
        if (
            a.decision_contractual == "SELECTED"
            and not a.operaciones_bian
            and normalizar(a.service_domain) in disponibles
        ):
            a.decision_contractual = "UNRESOLVED"
            a.motivo_decision = "NO_OPERATION_ANCHORED"
            a.reason_codes = list(dict.fromkeys([*a.reason_codes, NO_OPERATION_REASON_CODE]))
    return grupos


def aplicar_hallazgos_adversariales(
    grupos: ServiceDomainsDeHistoria,
    revision: RevisionAdversarialLLM,
    *,
    promovidos: frozenset[str] = frozenset(),
    degradados: frozenset[str] = frozenset(),
) -> tuple[ServiceDomainsDeHistoria, list[str]]:
    """Aplica la revisión adversarial de forma determinista.

    El revisor adversarial (LLM) es un asesor: por sí solo, un hallazgo aislado nunca decide nada
    aquí. Tres movimientos, todos gobernados por reglas ya evaluadas ANTES de llegar a esta
    función (esta función no re-decide nada, solo aplica lo ya decidido y anota trazabilidad):

    - DEGRADAR (`SELECTED` -> `UNRESOLVED`, catch-all conservador) para
      `DEPENDENCIA_PROMOVIDA_A_CONTRATO`/`DIRECTO_SIN_SERVICE_ROLE` cuando NO calificaron para la
      reclasificación determinista de abajo — el SD queda bloqueado para revisión humana en vez de
      publicarse, pero tampoco se reclasifica sin prueba independiente.
    - FINALIZAR una promoción ya decidida por `determinar_promociones` (`CONSUMED_DEPENDENCY` ->
      `OWNED_CONTRACT` reclasificado): si el SD promovido tiene evidencia BIAN oficial verificada,
      queda `SELECTED`/`OWNED_SELECTED` y se mueve a `candidatos_directos` aunque su score léxico
      crudo (heredado de la evaluación cuando el LLM lo enmarcaba como dependencia) siga en banda
      tentativa o incluso descartada — la barra de promoción ya es más estricta que el umbral
      numérico. Sin evidencia oficial verificada, se anota la promoción (`reason_codes`) pero se
      deja el grupo/decisión tal como salieron de la reclasificación (probablemente
      `UNRESOLVED`/`NO_OFFICIAL_BIAN_EVIDENCE`) — no se inventa una operación sobre evidencia
      inexistente.
    - ANOTAR una degradación ya decidida por `determinar_degradaciones` (`OWNED_CONTRACT` ->
      `CONSUMED_DEPENDENCY` reclasificado): a diferencia de la promoción, no hace falta mover nada
      a mano aquí — `_decidir` ya garantiza `REJECTED`/`CONSUMED_DEPENDENCY` en cuanto
      `rol_contractual` deja de ser `OWNED_CONTRACT`, sin importar el score. Solo se deja
      trazabilidad (`reason_codes`).

    Devuelve los grupos (posiblemente reordenados/movidos) y los `blocking_codes` a nivel de
    historia.
    """
    directos = list(grupos.candidatos_directos)
    tentativos = list(grupos.candidatos_tentativos)
    descartados = list(grupos.candidatos_descartados)
    por_sd = {normalizar(a.service_domain): a for a in (*directos, *tentativos, *descartados)}
    bloqueos_hu: list[str] = []

    for h in revision.hallazgos:
        codigos = list(
            dict.fromkeys(
                [
                    *h.reason_codes,
                    *([_DEGRADA_SELECTED[h.tipo]] if h.tipo in _DEGRADA_SELECTED else []),
                ]
            )
        )
        if h.tipo in ("CANDIDATO_OMITIDO", "OBJETO_SIN_PROPIETARIO", "EXCESO_DE_CONTRATOS"):
            bloqueos_hu.extend(codigos or [h.tipo])
        objetivo = por_sd.get(normalizar(h.service_domain)) if h.service_domain else None
        if objetivo is None:
            continue
        objetivo.reason_codes = list(dict.fromkeys([*objetivo.reason_codes, *codigos]))
        if h.detalle:
            objetivo.observaciones_adversariales = [
                *objetivo.observaciones_adversariales,
                f"[adversarial] {h.detalle}",
            ]
        if h.tipo in _DEGRADA_SELECTED and objetivo.decision_contractual == "SELECTED":
            objetivo.decision_contractual = "UNRESOLVED"
            objetivo.motivo_decision = "TENTATIVE_SCORE"
            objetivo.blocking_codes = list(dict.fromkeys([*objetivo.blocking_codes, *codigos]))

    for clave in promovidos:
        objetivo = por_sd.get(clave)
        if objetivo is None:
            continue
        objetivo.reason_codes = list(dict.fromkeys([*objetivo.reason_codes, PROMOTED_REASON_CODE]))
        objetivo.observaciones_adversariales = [
            *objetivo.observaciones_adversariales,
            "[adversarial] Promovido a OWNED_CONTRACT: accion directa con evidencia oficial y "
            "trazabilidad de escenarios, inicialmente clasificada como dependencia consumida.",
        ]
        # La barra de promoción (hallazgo independiente + dependency_kind de salida/resultado +
        # trazabilidad + evidencia citada + sin contradicción de Service Role) es más estricta que
        # el umbral numérico de "directo": si además la evidencia BIAN es oficial y verificable, el
        # score léxico crudo (heredado de cuando el LLM todavía enmarcaba esto como dependencia, y
        # por eso venía bajo en objeto/jerarquía) no debe dejarlo varado en tentativo/descartado.
        # Simétrico en sentido inverso al tope que ya aplica a los no-owned (`tope_no_owned`).
        if objetivo.evidencia_bian.estado in ("VERIFIED", "CACHED_VERIFIED"):
            _finalizar_como_directo(objetivo, directos, tentativos, descartados)

    for clave in degradados:
        objetivo = por_sd.get(clave)
        if objetivo is None:
            continue
        objetivo.reason_codes = list(dict.fromkeys([*objetivo.reason_codes, DEMOTED_REASON_CODE]))
        objetivo.observaciones_adversariales = [
            *objetivo.observaciones_adversariales,
            "[adversarial] Degradado a CONSUMED_DEPENDENCY: la acción citada no coincide con "
            "ninguna acción propia de la historia (extraída antes de proponer este SD); el rol "
            "OWNED_CONTRACT inicial no tiene sustento independiente.",
        ]

    for code in revision.blocking_codes:
        if code and code not in bloqueos_hu:
            bloqueos_hu.append(code)

    def _orden(a: ServiceDomainAsignado) -> tuple[float, str]:
        return (-a.confianza, a.service_domain.lower())

    grupos_salida = ServiceDomainsDeHistoria(
        candidatos_directos=sorted(directos, key=_orden),
        candidatos_tentativos=sorted(tentativos, key=_orden),
        candidatos_descartados=sorted(descartados, key=_orden),
    )
    return grupos_salida, list(dict.fromkeys(bloqueos_hu))
