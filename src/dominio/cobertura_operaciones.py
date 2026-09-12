"""Reglas de dominio deterministas para verificar cobertura de campos por operación BIAN.

Cierra el hueco entre "el operationId existe en el catálogo" (lo que ya validaba el código) y
"la operación realmente expone el dato que la historia necesita" (lo que antes solo decidía el
LLM, sin verificación). Puro: solo stdlib + `src.dominio` (nada de pydantic siquiera hace falta
aquí), respeta `test_arquitectura_hexagonal.py`.
"""

from __future__ import annotations

from src.dominio.historias import OperacionBian, SchemaBom
from src.dominio.normalizacion import normalizar


def campos_alcanzables(schema: str, schemas_detalle: list[SchemaBom]) -> set[str]:
    """Nombres de propiedad (normalizados) del schema raíz, 1 nivel — el mismo alcance que ya
    resuelve el caso real: `Reference.CellPhoneNumber` / `Reference.eMailAddress` son propiedades
    directas del schema `Reference`. Incluye el propio nombre del schema (normalizado) para que
    una cita al nombre del objeto raíz también cuente como evidencia."""
    clave = normalizar(schema)
    if not clave:
        return set()
    por_nombre = {normalizar(s.name): s for s in schemas_detalle}
    s = por_nombre.get(clave)
    if s is None:
        return {clave}
    return {clave} | {normalizar(p.name) for p in s.properties if p.name}


def operacion_evidencia_verificable(
    op: OperacionBian, evidence_refs: list[str], schemas_detalle: list[SchemaBom]
) -> bool:
    """¿Alguna `evidence_ref` citada por el LLM coincide con un campo real alcanzable desde el
    `response_schema` de `op`, o con el propio `grupo`/`operation_id`? Mismo patrón
    anti-alucinación que `_bom_respalda` (no acepta cualquier texto libre), aplicado a
    operaciones OFICIALES en vez de a BQ personalizados. No decide nada por sí sola: si no hay
    cita verificable, el llamador debe marcar la operación como no verificada, nunca descartarla
    en silencio ni sustituirla por otra (esa decisión semántica sigue siendo del LLM)."""
    if not evidence_refs:
        return False
    alcanzables = campos_alcanzables(op.response_schema, schemas_detalle) | {
        normalizar(op.grupo),
        normalizar(op.operation_id),
    }
    return any(normalizar(ref) in alcanzables for ref in evidence_refs if ref and ref.strip())


def derivar_path_grupo(grupo: str, verbo: str, operaciones: list[OperacionBian]) -> str | None:
    """Path para una operación NUEVA dentro de un CR/BQ ya existente: toma el `path` real de una
    operación existente de `grupo`, le quita el segmento final (su verbo) y agrega `verbo`. Así
    se reutiliza el prefijo real -incluido el nombre real del id-param, p.ej. `{referenceid}`- en
    vez de inventar un segmento genérico `/{id}`. Prefiere una operación "de instancia" (path con
    `{...}`, p.ej. `.../Reference/{referenceid}/Update`) sobre una "de colección" sin id
    (p.ej. `.../Evaluate`), porque una operación nueva sobre un objeto ya existente del grupo casi
    siempre necesita ese id. `None` si el grupo no tiene operaciones (no debería pasar: `grupo` se
    valida antes contra los CR/BQ ya presentes en el catálogo)."""
    clave = normalizar(grupo)
    existentes = [o for o in operaciones if normalizar(o.grupo) == clave]
    if not existentes:
        return None
    con_id = [o for o in existentes if "{" in o.path]
    base = (con_id[0] if con_id else existentes[0]).path.rsplit("/", 1)[0]
    return f"{base}/{verbo}"


def operation_id_en_uso(operation_id: str, operaciones: list[OperacionBian]) -> bool:
    """¿Ya existe ese operationId como operación OFICIAL real del Service Domain? Evita que una
    operación custom colisione con una oficial ya publicada."""
    clave = normalizar(operation_id)
    return any(normalizar(o.operation_id) == clave for o in operaciones)


_METODOS_HTTP = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def resolver_operation_id(id_propuesto: str, operaciones: list[OperacionBian]) -> OperacionBian | None:
    """Ancla un `operationId` propuesto por el LLM contra el catálogo REAL de `operaciones` de un
    Service Domain (ya filtrado a ese SD por el llamador).

    Match exacto primero (lo normal, y lo único que el prompt pide). Modelos más débiles de la
    cadena de failover a veces devuelven `"METODO /path/completo"` en vez del operationId
    (observado en producción: `"POST /Correspondence/{correspondenceid}/Outbound/Initiate"` en vez
    de `"InitiateOutbound"`). En ese caso se reconstruye desde el `path`/`method` REALES de una
    operación YA presente en `operaciones` — nunca desde texto libre ni fuzzy, y nunca inventa una
    operación que no esté en el catálogo dado (mismo principio anti-alucinación que
    `operacion_evidencia_verificable`: tolera un formato de cita distinto, no un contenido
    distinto). `None` si ninguna operación del catálogo coincide de ninguna forma."""
    directo = (id_propuesto or "").strip()
    if not directo:
        return None
    for o in operaciones:
        if o.operation_id == directo:
            return o
    clave = normalizar(directo)
    for o in operaciones:
        if normalizar(o.operation_id) == clave:
            return o
    partes = directo.split(None, 1)
    if len(partes) == 2 and partes[0].upper() in _METODOS_HTTP:
        metodo, ruta = partes[0].upper(), partes[1].strip()
        for o in operaciones:
            if o.path == ruta and o.method.upper() == metodo:
                return o
    for o in operaciones:
        if o.path == directo:
            return o
    return None
