"""Compara el resultado de una corrida contra un archivo de validación.

Mismo criterio que la suite E2E (`tests/e2e/shared/e2e_common.py`): se comparan los Service
Domains RELEVANTES (directos + tentativos) y sus operaciones por
`(operation_id, method, path, tipo, grupo)`. Se ignora a propósito todo lo narrativo
-razonamiento, justificación, scores, evidence_refs-, que cambia de corrida en corrida aunque el
resultado de negocio sea el mismo.

Vive en `api/` y no en `tests/` porque aquí la comparación es informativa: enseña las diferencias,
no rompe nada.
"""

from __future__ import annotations

from typing import Any

from api.modelos import ResumenComparacion


def _relevantes(historia: dict[str, Any]) -> dict[str, Any]:
    sd = historia.get("service_domains") or {}
    salida: dict[str, Any] = {}
    for grupo in ("candidatos_directos", "candidatos_tentativos"):
        for a in sd.get(grupo) or []:
            nombre = (a.get("service_domain") or "").strip()
            if nombre:
                salida[nombre.lower()] = a
    return salida


def _firmas_operacion(asignado: dict[str, Any]) -> set[tuple[str, ...]]:
    return {
        (
            str(o.get("operation_id") or ""),
            str(o.get("method") or ""),
            str(o.get("path") or ""),
            str(o.get("tipo") or ""),
            str(o.get("grupo") or ""),
        )
        for o in (asignado.get("operaciones_bian") or [])
    }


def comparar(resultado: dict[str, Any], esperado: dict[str, Any]) -> ResumenComparacion:
    """Qué Service Domains y operaciones del archivo de validación aparecen en el resultado."""
    hist_r = {h.get("archivo", ""): h for h in (resultado.get("historias") or [])}
    hist_e = {h.get("archivo", ""): h for h in (esperado.get("historias") or [])}

    # Las historias se emparejan por nombre de archivo; si el esperado viene de otra corrida con
    # otros nombres, se comparan por POSICIÓN antes que no comparar nada.
    comunes = [k for k in hist_e if k in hist_r]
    if not comunes and hist_e and hist_r:
        pares = list(zip(hist_e.values(), hist_r.values()))
    else:
        pares = [(hist_e[k], hist_r[k]) for k in comunes]

    if not pares:
        return ResumenComparacion(
            disponible=True,
            detalle="El archivo de validación no comparte ninguna historia con el resultado.",
        )

    esperados_tot = coincidentes = ops_tot = ops_ok = 0
    faltantes: list[str] = []
    inesperados: list[str] = []
    ops_faltantes: list[str] = []

    for he, hr in pares:
        rel_e, rel_r = _relevantes(he), _relevantes(hr)
        esperados_tot += len(rel_e)
        for clave, a_e in rel_e.items():
            a_r = rel_r.get(clave)
            nombre = a_e.get("service_domain", clave)
            if a_r is None:
                faltantes.append(f"{he.get('archivo','?')} · {nombre}")
                ops_tot += len(_firmas_operacion(a_e))
                ops_faltantes += [
                    f"{nombre} · {f[0]}" for f in sorted(_firmas_operacion(a_e))
                ]
                continue
            coincidentes += 1
            fe, fr = _firmas_operacion(a_e), _firmas_operacion(a_r)
            ops_tot += len(fe)
            ops_ok += len(fe & fr)
            ops_faltantes += [f"{nombre} · {f[0]}" for f in sorted(fe - fr)]
        for clave, a_r in rel_r.items():
            if clave not in rel_e:
                inesperados.append(f"{hr.get('archivo','?')} · {a_r.get('service_domain', clave)}")

    if esperados_tot == 0:
        detalle = "El archivo de validación no declara ningún Service Domain relevante."
    elif coincidentes == esperados_tot and ops_ok == ops_tot:
        detalle = "El resultado reproduce la validación: mismos Service Domains y mismas operaciones."
    else:
        detalle = (
            f"Coinciden {coincidentes} de {esperados_tot} Service Domains y "
            f"{ops_ok} de {ops_tot} operaciones. Lo 'inesperado' no es un error: una corrida "
            f"posterior puede ampliar cobertura."
        )

    return ResumenComparacion(
        disponible=True,
        historias_comparadas=len(pares),
        service_domains_esperados=esperados_tot,
        service_domains_coincidentes=coincidentes,
        faltantes=faltantes,
        inesperados=inesperados,
        operaciones_esperadas=ops_tot,
        operaciones_coincidentes=ops_ok,
        operaciones_faltantes=ops_faltantes,
        detalle=detalle,
    )
