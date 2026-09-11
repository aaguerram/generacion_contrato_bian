"""Normalización de nombres de Service Domain para la coincidencia exacta."""

from __future__ import annotations

import re

_NO_ALFANUM = re.compile(r"[^a-z0-9]+")


def normalizar(nombre: str) -> str:
    """'Issued Device Administration', 'IssuedDeviceAdministration',
    'ISSUED_DEVICE_ADMINISTRATION' -> 'issueddeviceadministration'."""
    return _NO_ALFANUM.sub("", (nombre or "").lower())


def construir_indice_exacto(nombres: list[str]) -> dict[str, str]:
    """{ nombre_normalizado -> nombre_canónico }."""
    return {normalizar(n): n for n in nombres}
