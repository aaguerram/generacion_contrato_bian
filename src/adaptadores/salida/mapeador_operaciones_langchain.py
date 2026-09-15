"""Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia y detecta
brechas CR/BQ-vs-BOM (operación personalizada propuesta dentro de un CR/BQ existente, si el BOM
lo respalda).

Contexto del prompt = las operaciones de los Service Domains directos con catálogo local
(cada una con los campos alcanzables de su propio `response_schema`, resueltos desde
`schemas_detalle` — sin esto el LLM tiene que cruzar mentalmente dos bloques separados y, si el
bloque de schemas se trunca, elige por parecido de nombre en vez de evidencia real) + el BOM
completo (schemas con cuerpo + modelo de clases PUML) para el fallback de brechas. Blindaje
anti-alucinación: se descarta cualquier (service_domain, operation_id) que no esté en la lista
provista; una operación personalizada para un Service Domain no reconocido también se descarta.
La validación PROFUNDA contra el BOM (¿existe de verdad esa clase/atributo?, ¿el grupo citado
existe de verdad?) la hace el código en la capa de aplicación, no el adaptador. Adjunta
`MetadatosPrompt` para reproducibilidad.
"""

from __future__ import annotations

import hashlib
import logging
import time

from src.adaptadores.salida.formato_bom import formatear_bom_puml, formatear_schemas_bom
from src.adaptadores.salida.llm.failover import SoportaStructured
from src.adaptadores.salida.prompts_mapeo import SPEC_OPERACIONES
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.dominio.cobertura_operaciones import resolver_operation_id
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

_MAX_CAMPOS_RESPUESTA = 15


def _campos_respuesta(o: OperacionBian, indice_schemas: dict) -> str:
    """`campos_respuesta={eMailAddress:ContactPoint, CellPhoneNumber:ContactPoint, ...}` del
    `response_schema` real de `o`, resuelto desde `schemas_detalle` -ya cargado en el paquete de
    evidencia, sin llamada extra-. Vacío si no hay `response_schema` o no se pudo resolver."""
    schema = indice_schemas.get(normalizar(o.response_schema)) if o.response_schema else None
    if schema is None or not schema.properties:
        return ""
    props = ", ".join(f"{p.name}:{p.ref or p.type}" if (p.ref or p.type) else p.name
                       for p in schema.properties[:_MAX_CAMPOS_RESPUESTA])
    extra = len(schema.properties) - _MAX_CAMPOS_RESPUESTA
    if extra > 0:
        props += f", …(+{extra})"
    return f"campos_respuesta={{{props}}}"


def _formatear(
    operaciones_por_sd: dict[str, list[OperacionBian]],
    paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato],
) -> str:
    bloques = []
    for sd, operaciones in operaciones_por_sd.items():
        paquete = paquetes_por_sd.get(sd)
        indice_schemas = {normalizar(s.name): s for s in paquete.schemas_detalle} if paquete else {}
        lineas = [f'Service Domain "{sd}":']
        # Numeradas: el prompt acepta el índice como cita, y elegir un número de una lista es
        # mucho más fácil para un modelo pequeño que reproducir un operationId camelCase entre
        # decenas. `resolver_operation_id` lo ancla contra ESTA misma lista, así que sigue siendo
        # una cita al catálogo real (un índice fuera de rango no resuelve nada).
        for posicion, o in enumerate(operaciones, start=1):
            padre = f" <- {o.parent_control_record}" if o.parent_control_record else ""
            esquema = " / ".join(p for p in (
                f"req={o.request_schema}" if o.request_schema else "",
                f"resp={o.response_schema}" if o.response_schema else "",
            ) if p)
            campos = _campos_respuesta(o, indice_schemas)
            resumen = f"  {o.summary}" if o.summary else ""
            lineas.append(
                f'  - {o.operation_id}  ({o.method} {o.path})  [{o.tipo} {o.grupo}{padre}]'
                + (f"  {esquema}" if esquema else "")
                + (f"  {campos}" if campos else "")
                + resumen
            )
        bloques.append("\n".join(lineas))
    return "\n\n".join(bloques)


def _formatear_bom(
    operaciones_por_sd: dict[str, list[OperacionBian]],
    paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato],
) -> str:
    bloques = []
    for sd, paquete in paquetes_por_sd.items():
        priorizar = {
            normalizar(s) for o in operaciones_por_sd.get(sd, [])
            for s in (o.request_schema, o.response_schema) if s
        }
        bloques.append(
            f'Service Domain "{sd}":\n'
            f"  schemas_bom:\n{formatear_schemas_bom(paquete.schemas_detalle, priorizar=priorizar)}\n"
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
        self._chat_model = chat_model
        self._cadena = SPEC_OPERACIONES.template | chat_model.with_structured_output(MapeoOperacionesLLM)
        self._modelo_desc = modelo_desc
        self._temperature = temperature
        self._catalog_sha256 = catalog_sha256

    def _huella(self, historia: str, uso=None) -> MetadatosPrompt:
        return MetadatosPrompt(
            prompt_id=SPEC_OPERACIONES.id,
            prompt_version=SPEC_OPERACIONES.version,
            prompt_sha256=hashlib.sha256(SPEC_OPERACIONES.texto.encode("utf-8")).hexdigest(),
            nodo="seleccionar_operaciones",
            historia=historia,
            model=self._modelo_desc,
            provider_used=uso.proveedor if uso else "",
            model_used=uso.modelo if uso else "",
            attempt=uso.intento if uso else None,
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

        inicio = time.monotonic()
        try:
            resultado: MapeoOperacionesLLM = self._cadena.invoke(
                {
                    "funcionalidad_macro": funcionalidad.funcionalidad_macro,
                    "historia_archivo": historia.archivo,
                    "historia_titulo": historia.titulo,
                    "historia_contenido": historia.contenido,
                    "operaciones": _formatear(operaciones_por_sd, paquetes_por_sd),
                    "bom_por_sd": _formatear_bom(operaciones_por_sd, paquetes_por_sd),
                }
            )
            uso = self._chat_model.ultimo_uso() if hasattr(self._chat_model, "ultimo_uso") else None
        finally:
            logger.info("TIEMPO_LLM nodo=%s tardo=%.1fs", SPEC_OPERACIONES.id, time.monotonic() - inicio)

        catalogo_por_sd = {normalizar(sd): operaciones for sd, operaciones in operaciones_por_sd.items()}
        limpias: list = []
        descartadas: list[str] = []
        for op in resultado.operaciones:
            operaciones_sd = catalogo_por_sd.get(normalizar(op.service_domain))
            # `resolver_operation_id` (no un chequeo exacto): modelos más débiles del failover a
            # veces devuelven "METODO /path" en vez del operationId literal que pide el prompt --
            # se tolera ese formato reconstruyéndolo desde el path/method REALES de una operación
            # ya presente en `operaciones_sd`, nunca inventando una operación nueva ni cruzando a
            # otro Service Domain (mismo blindaje anti-alucinación, formato de cita más tolerante).
            if operaciones_sd and resolver_operation_id(op.operation_id, operaciones_sd) is not None:
                limpias.append(op)
            else:
                # No basta con loguearlo: si el modelo se inventa TODAS las operaciones, la
                # corrida acaba con cero ancladas y sin ninguna señal de por qué. La cita viaja
                # de vuelta para que el servicio la convierta en incidencia.
                descartadas.append(f"{op.service_domain}/{op.operation_id}")
                logger.warning(
                    "HU '%s': operación %s/%s fuera del catálogo provisto; descartada",
                    historia.titulo,
                    op.service_domain,
                    op.operation_id,
                )

        sd_conocidos = set(catalogo_por_sd) | {normalizar(sd) for sd in paquetes_por_sd}
        bqs = []
        for bq in resultado.bq_personalizados:
            if normalizar(bq.service_domain) in sd_conocidos:
                bqs.append(bq)
            else:
                logger.warning(
                    "HU '%s': operación personalizada en grupo '%s' para un Service Domain no "
                    "reconocido ('%s'); descartada",
                    historia.titulo, bq.grupo_existente, bq.service_domain,
                )

        return resultado.model_copy(update={
            "operaciones": limpias,
            "bq_personalizados": bqs,
            "citas_descartadas": descartadas,
            "metadatos": self._huella(historia.archivo, uso),
        })
