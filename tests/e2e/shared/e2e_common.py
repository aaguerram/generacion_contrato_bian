"""Utilidades compartidas por TODAS las pruebas E2E reales (LLM real, sin mocks, sin
`--proveedor fake`).

Bajo demanda (nunca en la suite por defecto -- llamadas LLM reales, consumen cuota):

    EJECUTAR_E2E=1 .venv/Scripts/python -m unittest discover -s tests -p "test_e2e_*.py" -v

## Regla para toda prueba E2E nueva

`tests/resources/<caso>/` es autocontenida y trae SIEMPRE estos archivos:

- `<algo>.txt` / `.md` / `.markdown` -> la(s) Historia(s) de Usuario (HU) de este caso
  (las lee `LectorHistoriasFilesystem`, no este módulo).
- `funcionalidad-*.json` -> la funcionalidad macro. Autodescubierta por `ejecutar_caso()`:
  debe haber EXACTAMENTE un archivo con ese patrón por carpeta.
- `expected-result.json` -> una corrida de referencia COMPLETA (misma forma que
  `mapeo-historias-service-domains.json`, es decir, un `ResultadoMapeoHistorias` serializado),
  curada a mano por quien arma el caso -- normalmente copiando una corrida real que ya se validó
  como correcta. **Nunca lo escribe ni lo sobreescribe el pipeline.**

El pipeline real SÍ sigue escribiendo su salida completa (`mapeo-historias-service-domains.json`)
en la misma carpeta en cada corrida -- es el artefacto "actual" (inspeccionable, se sobreescribe),
deliberadamente distinto del "expected" de arriba (si el test comparara contra un archivo que el
propio pipeline acaba de escribir, nunca podría fallar tras la primera corrida).

`verificar_candidatos_y_operaciones()` compara la corrida actual contra `expected-result.json` en
dos ejes, ignorando todo lo narrativo (razonamiento, justificacion, escenarios_hu, ...) que varía
de corrida a corrida aunque el resultado de negocio sea el mismo:

1. Los Service Domain relevantes de la referencia (`directos` + `tentativos`) deben seguir
   presentes como `directos` o `tentativos`. Los descartados son hipótesis del LLM y no forman
   parte del contrato funcional estable.
2. Para cada Service Domain relevante, todas las `operaciones_bian` de referencia deben seguir
   ancladas, comparadas por `(operation_id, method, path, tipo, grupo)`. Se permiten operaciones
   adicionales válidas porque una corrida posterior puede aumentar cobertura.

Estructura de carpetas (regla para toda prueba E2E nueva):

    tests/
      e2e/
        shared/
          e2e_common.py          <- este archivo
        test_e2e_<caso>.py        <- usa lo de arriba, sin literales de negocio hardcodeados
      resources/
        <caso>/                  <- autocontenida, ver arriba
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from src.configuracion.contenedor import crear_caso_uso_mapeo
from src.configuracion.settings import cargar_settings
from src.dominio.historias import (
    HistoriaConServiceDomains,
    ResultadoMapeoHistorias,
    ServiceDomainAsignado,
)
from src.dominio.normalizacion import normalizar

RESOURCES = Path(__file__).resolve().parents[2] / "resources"

# El harness llamaba a `cargar_settings()` sin argumentos, así que una prueba E2E solo podía
# correr contra el `config.yaml` de la raíz: comparar "con los flags nuevos" contra "sin ellos"
# obligaba a editar el archivo versionado entre corridas. `MAPEO_CONFIG` apunta a otro YAML sin
# tocar el del repo; sin la variable, el comportamiento es exactamente el de antes.
VAR_CONFIG = "MAPEO_CONFIG"

requiere_e2e = unittest.skipUnless(
    os.environ.get("EJECUTAR_E2E") == "1",
    "prueba de integracion bajo demanda (llamadas LLM reales, consume cuota) -> "
    "EJECUTAR_E2E=1 para correrla explicitamente",
)

_FirmaOperacion = tuple[str, str, str, str, str]  # (operation_id, method, path, tipo, grupo)


def _funcionalidad_de(carpeta: Path) -> Path:
    candidatos = sorted(carpeta.glob("funcionalidad-*.json"))
    if len(candidatos) != 1:
        raise FileNotFoundError(
            f"Se esperaba exactamente un 'funcionalidad-*.json' en {carpeta}; "
            f"encontrados: {[c.name for c in candidatos]}"
        )
    return candidatos[0]


def ejecutar_caso(carpeta: str) -> ResultadoMapeoHistorias:
    """Ejecuta `mapear-historias` (LLM real, failover de `config.yaml`) sobre
    `tests/resources/<carpeta>/`. Autodescubre el JSON de funcionalidad (debe haber uno
    solo en la carpeta). Usa el `config.yaml` de la raíz salvo que `MAPEO_CONFIG` apunte a otro (así se compara una
    configuración candidata sin editar el archivo versionado).
    `--directorio-hu` y `--directorio` (salida) son la MISMA carpeta:
    `leer_historias()` solo lee `.txt`/`.md`/`.markdown`, así que ignora los JSON que ya
    viven ahí (funcionalidad, expected-result, y la salida anterior)."""
    datos = RESOURCES / carpeta
    if not datos.is_dir():
        raise FileNotFoundError(f"falta la carpeta de datos de la prueba: {datos}")
    ruta_funcionalidad = _funcionalidad_de(datos)

    ruta_config = os.environ.get(VAR_CONFIG) or None
    if ruta_config and not Path(ruta_config).is_file():
        raise FileNotFoundError(f"{VAR_CONFIG}={ruta_config} no existe")
    config = cargar_settings(ruta_config=ruta_config)
    caso_uso = crear_caso_uso_mapeo(config)
    return caso_uso.ejecutar(str(datos), str(ruta_funcionalidad), str(datos))


def cargar_esperado(carpeta: str) -> ResultadoMapeoHistorias:
    """Lee `tests/resources/<carpeta>/expected-result.json` -- una corrida de referencia
    COMPLETA, curada a mano. Falla fuerte si no existe: una prueba E2E sin este archivo no
    tiene con qué comparar."""
    ruta = RESOURCES / carpeta / "expected-result.json"
    if not ruta.is_file():
        raise FileNotFoundError(
            f"falta expected-result.json en {ruta.parent} -- toda prueba E2E necesita uno "
            "(ver docstring de tests/e2e/shared/e2e_common.py)"
        )
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return ResultadoMapeoHistorias.model_validate(datos)


def _candidatos_por_sd(hu: HistoriaConServiceDomains) -> dict[str, ServiceDomainAsignado]:
    """Todos los Service Domain evaluados para una historia, sin importar el grupo (directo/
    tentativo/descartado) -- la comparación de candidatos es sobre TODA la evaluación."""
    todos = (
        *hu.service_domains.candidatos_directos,
        *hu.service_domains.candidatos_tentativos,
        *hu.service_domains.candidatos_descartados,
    )
    return {a.service_domain: a for a in todos}


def _firma_operaciones(asignado: ServiceDomainAsignado) -> frozenset[_FirmaOperacion]:
    """El contrato oficial de cada operación anclada: operation_id/method/path/tipo/grupo,
    NUNCA el texto libre (justificacion/evidence_refs/traceability/escenarios_hu) que puede
    variar de corrida a corrida aunque la operación anclada sea la misma."""
    return frozenset(
        (op.operation_id, op.method, op.path, op.tipo, op.grupo) for op in asignado.operaciones_bian
    )


def verificar_candidatos_y_operaciones(
    testcase: unittest.TestCase,
    resultado: ResultadoMapeoHistorias,
    esperado: ResultadoMapeoHistorias,
) -> None:
    """Comprueba el contrato funcional estable de una corrida de referencia.

    Solo los candidatos directos/tentativos de la referencia son obligatorios. Los descartados
    son hipótesis negativas y su presencia depende del modelo que responda dentro del failover.
    Las operaciones de referencia son un subconjunto obligatorio: una cobertura adicional
    correctamente anclada no constituye una regresión.
    """
    # El nombre de un fixture puede atravesar ZIP/Git/filesystems con distinta representación
    # Unicode (p. ej. "actualización" vs "actualizacion"). La identidad se normaliza; el
    # contenido funcional y las operaciones siguen comparándose sin relajar sus valores.
    esperadas_por_hu = {normalizar(h.archivo): h for h in esperado.historias}
    actuales_por_hu = {normalizar(h.archivo): h for h in resultado.historias}
    testcase.assertEqual(
        set(actuales_por_hu),
        set(esperadas_por_hu),
        "el conjunto de historias procesadas no coincide con el esperado",
    )

    for identidad_archivo, hu_esperada in esperadas_por_hu.items():
        hu_actual = actuales_por_hu[identidad_archivo]
        archivo = hu_actual.archivo
        sds_esperados = {
            a.service_domain: a
            for a in (
                *hu_esperada.service_domains.candidatos_directos,
                *hu_esperada.service_domains.candidatos_tentativos,
            )
        }
        sds_actuales = {
            a.service_domain: a
            for a in (
                *hu_actual.service_domains.candidatos_directos,
                *hu_actual.service_domains.candidatos_tentativos,
            )
        }

        testcase.assertTrue(
            set(sds_esperados) <= set(sds_actuales),
            f"HU '{archivo}': faltan Service Domain relevantes de la referencia\n"
            f"  requeridos: {sorted(sds_esperados)}\n"
            f"  actuales:   {sorted(sds_actuales)}",
        )

        for sd_nombre, asignado_esperado in sds_esperados.items():
            asignado_actual = sds_actuales[sd_nombre]
            firma_esperada = _firma_operaciones(asignado_esperado)
            firma_actual = _firma_operaciones(asignado_actual)
            testcase.assertTrue(
                firma_esperada <= firma_actual,
                f"HU '{archivo}' / SD '{sd_nombre}': faltan operaciones_bian requeridas "
                f"(operationId/method/path/tipo/grupo)\n"
                f"  requeridas: {sorted(firma_esperada)}\n"
                f"  actuales:   {sorted(firma_actual)}",
            )
