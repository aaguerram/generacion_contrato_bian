"""Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia y detecta
brechas CR/BQ-vs-BOM (BQ personalizado propuesto, si el BOM lo respalda).

Contexto del prompt = las operaciones de los Service Domains directos con catálogo local +
su BOM (schemas con cuerpo + modelo de clases PUML). Blindaje anti-alucinación: se descarta
cualquier (service_domain, operation_id) que no esté en la lista provista; un `bq_personalizados`
de un Service Domain no reconocido también se descarta. La validación PROFUNDA contra el BOM
(¿existe de verdad esa clase/atributo?) la hace el código en la capa de aplicación, no el adaptador.
Adjunta `MetadatosPrompt` para reproducibilidad.
"""

from __future__ import annotations

import hashlib
import logging

from src.adaptadores.salida.formato_bom import formatear_bom_puml, formatear_schemas_bom
from src.adaptadores.salida.llm.failover import SoportaStructured
from src.adaptadores.salida.prompts_mapeo import SPEC_OPERACIONES
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.dominio.historias import (
    FuncionalidadMacro,
    HistoriaUsuario,
    MapeoOperacionesLLM,
    MetadatosPrompt,
    OperacionBian,
    PaqueteEvidenciaCandidato,
)
from src.dominio.normalizacion import normalizar

logger = logging.getLogger(__name__)


def _formatear(operaciones_por_sd: dict[str, list[OperacionBian]]) -> str:
    bloques = []
    for sd, operaciones in operaciones_por_sd.items():
        lineas = [f'Service Domain "{sd}":']
        for o in operaciones:
            padre = f" <- {o.parent_control_record}" if o.parent_control_record else ""
            esquema = " / ".join(p for p in (
                f"req={o.request_schema}" if o.request_schema else "",
                f"resp={o.response_schema}" if o.response_schema else "",
            ) if p)
            resumen = f"  {o.summary}" if o.summary else ""
            lineas.append(
                f'  - {o.operation_id}  ({o.method} {o.path})  [{o.tipo} {o.grupo}{padre}]'
                + (f"  {esquema}" if esquema else "") + resumen
            )
        bloques.append("\n".join(lineas))
    return "\n\n".join(bloques)


def _formatear_bom(paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato]) -> str:
    bloques = []
    for sd, paquete in paquetes_por_sd.items():
        bloques.append(
            f'Service Domain "{sd}":\n'
            f"  schemas_bom:\n{formatear_schemas_bom(paquete.schemas_detalle)}\n"
            f"  modelo_bom_puml:\n{formatear_bom_puml(paquete.bom_modelo)}"
        )
    return "\n\n".join(bloques) if bloques else "(sin paquetes de evidencia)"


class MapeadorOperacionesLangChain(MapeadorOperacionesBianPort):
    def __init__(
        self,
        chat_model: SoportaStructured,
        *,
        modelo_desc: str = "",
        temperature: float | None = None,
        catalog_sha256: str = "",
    ) -> None:
        self._cadena = SPEC_OPERACIONES.template | chat_model.with_structured_output(MapeoOperacionesLLM)
        self._modelo_desc = modelo_desc
        self._temperature = temperature
        self._catalog_sha256 = catalog_sha256

    def _huella(self, historia: str) -> MetadatosPrompt:
        return MetadatosPrompt(
            prompt_id=SPEC_OPERACIONES.id,
            prompt_version=SPEC_OPERACIONES.version,
            prompt_sha256=hashlib.sha256(SPEC_OPERACIONES.texto.encode("utf-8")).hexdigest(),
            nodo="seleccionar_operaciones",
            historia=historia,
            model=self._modelo_desc,
            temperature=self._temperature,
            catalog_sha256=self._catalog_sha256,
        )

    def mapear(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        operaciones_por_sd: dict[str, list[OperacionBian]],
        paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato],
    ) -> MapeoOperacionesLLM:
        if not operaciones_por_sd:
            return MapeoOperacionesLLM(operaciones=[], metadatos=self._huella(historia.archivo))

        resultado: MapeoOperacionesLLM = self._cadena.invoke(
            {
                "funcionalidad_macro": funcionalidad.funcionalidad_macro,
                "historia_archivo": historia.archivo,
                "historia_titulo": historia.titulo,
                "historia_contenido": historia.contenido,
                "operaciones": _formatear(operaciones_por_sd),
                "bom_por_sd": _formatear_bom(paquetes_por_sd),
            }
        )

        validos = {
            normalizar(sd): {o.operation_id for o in operaciones}
            for sd, operaciones in operaciones_por_sd.items()
        }
        limpias = []
        for op in resultado.operaciones:
            permitidas = validos.get(normalizar(op.service_domain))
            if permitidas and op.operation_id in permitidas:
                limpias.append(op)
            else:
                logger.warning(
                    "HU '%s': operación %s/%s fuera del catálogo provisto; descartada",
                    historia.titulo,
                    op.service_domain,
                    op.operation_id,
                )

        sd_conocidos = set(validos) | {normalizar(sd) for sd in paquetes_por_sd}
        bqs = []
        for bq in resultado.bq_personalizados:
            if normalizar(bq.service_domain) in sd_conocidos:
                bqs.append(bq)
            else:
                logger.warning(
                    "HU '%s': BQ personalizado '%s' para un Service Domain no reconocido ('%s'); descartado",
                    historia.titulo, bq.nombre_bq, bq.service_domain,
                )

        return resultado.model_copy(update={
            "operaciones": limpias, "bq_personalizados": bqs, "metadatos": self._huella(historia.archivo),
        })
