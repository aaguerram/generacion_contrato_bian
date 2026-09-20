"""Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`.

Un solo puerto con un método por nodo LLM del subgrafo (extracción -> [enrutamiento] ->
candidatos -> completitud -> evaluación por candidato -> revisión adversarial -> reconciliación). El
adaptador construye cada prompt SOLO con la evidencia que recibe (catálogo local + paquete
de evidencia oficial por candidato); no puede aportar conocimiento externo. El scoring, los
umbrales y la decisión final son deterministas (capa de dominio), nunca del LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import (
    CandidatosHistoriaLLM,
    EnrutamientoDominiosLLM,
    EvaluacionCandidatoLLM,
    FuncionalidadMacro,
    HistoriaUsuario,
    IntencionHistoriaLLM,
    PaqueteEvidenciaCandidato,
    ReconciliacionFuncionalidadLLM,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
    ServiceDomainsDeHistoria,
)
from src.dominio.modelos import EntradaCatalogo


class AnalistaMapeoBianPort(ABC):
    @abstractmethod
    def extraer_intencion(
        self, historia: HistoriaUsuario, funcionalidad: FuncionalidadMacro
    ) -> IntencionHistoriaLLM:
        """Nodo 1: interpreta la historia. Sin nombres de Service Domain, sin decisiones BIAN."""

    def enrutar_dominios(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        intencion: IntencionHistoriaLLM,
        catalogo: list[EntradaCatalogo],
    ) -> EnrutamientoDominiosLLM:
        """Nodo 2a (opcional): elige Business Domains sobre la taxonomía, antes de ver ningún SD.

        NO es abstracto a propósito: enrutar es una estrategia, no un requisito del puerto. Un
        adaptador que no la implemente devuelve un enrutamiento vacío, que el caso de uso
        interpreta como "sin filtrar" -- el catálogo completo, que es el comportamiento histórico.
        """
        return EnrutamientoDominiosLLM()

    @abstractmethod
    def generar_candidatos(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        intencion: IntencionHistoriaLLM,
        catalogo: list[EntradaCatalogo],
        *,
        texto_completo: bool = False,
        totales_por_dominio: dict[str, int] | None = None,
        propietarios_bom: list | None = None,
        grupo: str | None = None,
    ) -> CandidatosHistoriaLLM:
        """Nodo 2b: propone nombres de Service Domain del catálogo. Es una PISTA, no exhaustiva.

        `grupo` (nombre del grupo del fan-out) llega solo con `candidatos_por_dominio`: el
        catálogo es UNA parte y el prompt debe decirlo (vacío es válido; lo ausente no es gap).

        `propietarios_bom` (`list[CandidatoClaseBom]`) llega solo con el flag
        `evidencia_bom_en_candidatos`: la evidencia del canal de propiedad de clases BOM del nodo
        2a, para que 2b sepa POR QUÉ un Service Domain rescatado está en el catálogo.

        `totales_por_dominio` (Business Domain -> nº real de SD) llega solo con routing: el
        catálogo acotado puede traer dominios abiertos a medias (propietarios rescatados por el
        canal de propiedad de clases BOM) y el adaptador lo dice en la taxonomía.

        `texto_completo` = el catálogo recibido ya viene acotado (viene de `enrutar_dominios`), así
        que cabe escribirlo SIN recortar: rol entero + `examples_of_use` + `features`. Es donde
        está la ganancia del routing -- no en mirar menos, sino en poder mostrarlo todo.
        """

    @abstractmethod
    def revisar_completitud(
        self,
        historia: HistoriaUsuario,
        intencion: IntencionHistoriaLLM,
        candidatos: CandidatosHistoriaLLM,
        catalogo: list[EntradaCatalogo],
        disponibilidad_evidencia: dict[str, str],
    ) -> RevisionCompletitudLLM:
        """Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes /
        no soportados / conflictos de ownership / responsabilidades duplicadas."""

    @abstractmethod
    def evaluar_candidato(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        intencion: IntencionHistoriaLLM,
        paquete: PaqueteEvidenciaCandidato,
    ) -> EvaluacionCandidatoLLM:
        """Nodo 4: evalúa UN candidato contra SU paquete de evidencia oficial cerrado.
        Devuelve señales ordinales 0-3 + trazabilidad ownership/dependency separada. Sin confianza."""

    @abstractmethod
    def revisar_adversarial(
        self,
        historia: HistoriaUsuario,
        intencion: IntencionHistoriaLLM,
        grupos: ServiceDomainsDeHistoria,
    ) -> RevisionAdversarialLLM:
        """Nodo 5: prompt DISTINTO que revisa la hipótesis ya clasificada (acción directa como
        dependencia, objeto sin propietario, dependencia promovida a contrato, candidato omitido...)."""

    @abstractmethod
    def reconciliar_funcionalidad(
        self,
        funcionalidad: FuncionalidadMacro,
        resumen_por_historia: list[dict],
    ) -> ReconciliacionFuncionalidadLLM:
        """Nodo 7 (1 sola vez): ve todas las historias y propone el rol de cada SD a nivel de
        funcionalidad. Es un ASESOR: el código decide el estado final."""
