#!/usr/bin/env python3
"""
Configura el CLI `memanto` en esta maquina para usar el servidor MEMANTO
on-prem compartido de Produbanco (Docker + Moorcheh, desplegado via
docker-compose en super@100.102.221.79:/home/super/Desktop/claude_cli/openwebui/memanto,
alcanzable por Tailscale) con un namespace/agente dedicado a este proyecto,
para que no se mezcle con la memoria de otros proyectos que usen el mismo
servidor.

Uso (una vez por maquina, tras clonar el repo):
    python scripts/setup_memanto.py

Que hace:
  1. Instala el paquete `memanto` si falta (pip install memanto).
  2. Escribe ~/.memanto/config.yaml -> backend: on-prem (sin tocar otras
     claves que ya existan ahi).
  3. Escribe ~/.memanto/on-prem/state.json -> url del servidor remoto
     (no toca embedding/llm si ya estaban configurados, para no romper un
     setup on-prem local que el usuario ya tuviera para OTRO proyecto).
  4. Crea (o activa, si ya existe) el agente/namespace de este proyecto.
  5. `memanto connect codex --project-dir .` (idempotente): asegura que
     AGENTS.md + .agents/skills/memanto/ existan, para que Codex CLI sepa
     usar MEMANTO igual que Claude Code (via ~/.claude/CLAUDE.md global).
  6. `memanto memory sync --project-dir .`: refresca MEMORY.md (snapshot
     estatico versionado, util como fallback aunque el CLI no este activo).

Nota: `~/.memanto/on-prem/state.json` es global a la maquina -> solo puede
apuntar a UN servidor on-prem a la vez. Si en esta maquina usas MEMANTO
on-prem para otro proyecto con OTRO servidor, este script re-apunta la
maquina hacia el servidor de Produbanco; el namespace (agente) de cada
proyecto sigue siendo independiente y no se borra.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# Servidor MEMANTO on-prem compartido (Moorcheh, puerto 8080), alcanzable
# por Tailscale. El docker-compose real corre en el servidor, en
# /home/super/Desktop/claude_cli/openwebui/memanto/docker-compose.yml.
SERVER_URL = "http://100.102.221.79:8080"

# Namespace/agente MEMANTO dedicado a este proyecto. En Moorcheh esto crea
# el namespace `memanto_agent_{AGENT_ID}`, aislado del resto de proyectos
# que compartan el mismo servidor.
AGENT_ID = "generacion-contrato-ia-v2"
AGENT_DESCRIPTION = (
    "Memoria del proyecto generacion_contrato_ia_v2 "
    "(Produbanco - generacion de contratos BIAN via IA)"
)

# Deben coincidir con los defaults del docker-compose del servidor
# (EMBEDDING_MODEL / LLM_MODEL) para que `memanto answer` use el modelo
# realmente servido por el Ollama del backend.
DEFAULT_EMBEDDING_PROVIDER = "ollama"
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:8b"
DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_LLM_MODEL = "qwen3.8:27b-q8_0"

MEMANTO_HOME = Path.home() / ".memanto"

# Raiz del proyecto (padre de scripts/), para que --project-dir sea correcto
# sin importar desde donde se invoque este script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_memanto_installed() -> None:
    if shutil.which("memanto") is not None:
        print("[ok] memanto CLI ya instalado")
        return
    print("[..] instalando paquete 'memanto' (pip install memanto)")
    result = _run([sys.executable, "-m", "pip", "install", "memanto"])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit("No se pudo instalar memanto. Revisa el error de pip arriba.")
    print("[ok] memanto instalado")


def configure_backend() -> None:
    import yaml  # PyYAML - ya es dependencia del proyecto

    config_file = MEMANTO_HOME / "config.yaml"
    MEMANTO_HOME.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if config_file.exists():
        try:
            data = yaml.safe_load(config_file.read_text()) or {}
        except Exception:
            data = {}
    memanto_section = data.get("memanto")
    if not isinstance(memanto_section, dict):
        memanto_section = {}
    memanto_section["backend"] = "on-prem"
    data["memanto"] = memanto_section

    config_file.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False)
    )
    print(f"[ok] backend on-prem escrito en {config_file}")


def configure_onprem_state() -> None:
    state_dir = MEMANTO_HOME / "on-prem"
    state_file = state_dir / "state.json"
    state_dir.mkdir(parents=True, exist_ok=True)

    state: dict = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            state = {}

    state["url"] = SERVER_URL
    state.setdefault("embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
    state.setdefault("embedding_model", DEFAULT_EMBEDDING_MODEL)
    state.setdefault("llm_provider", DEFAULT_LLM_PROVIDER)
    state.setdefault("llm_model", DEFAULT_LLM_MODEL)

    state_file.write_text(json.dumps(state, indent=2))
    print(f"[ok] servidor on-prem ({SERVER_URL}) escrito en {state_file}")


def create_or_activate_agent() -> None:
    result = _run(
        [
            "memanto",
            "agent",
            "create",
            AGENT_ID,
            "--pattern",
            "project",
            "--description",
            AGENT_DESCRIPTION,
        ]
    )
    output = result.stdout + result.stderr
    if result.returncode == 0:
        print(output)
        print(f"[ok] agente/namespace '{AGENT_ID}' creado y activado")
        return

    if "already exists" in output.lower():
        print(f"[ok] agente '{AGENT_ID}' ya existia, activandolo")
        activate = _run(["memanto", "agent", "activate", AGENT_ID])
        print(activate.stdout + activate.stderr)
        if activate.returncode != 0:
            raise SystemExit("No se pudo activar el agente existente.")
        return

    print(output)
    raise SystemExit("No se pudo crear el agente. Revisa el error arriba.")


def connect_codex() -> None:
    """Deploy AGENTS.md + skill so Codex CLI also knows to use MEMANTO.

    Idempotent: memanto keeps a MEMANTO-MANAGED-SECTION marker in AGENTS.md
    and just updates it in place on re-runs.
    """
    result = _run(["memanto", "connect", "codex", "--project-dir", str(PROJECT_ROOT)])
    print(result.stdout + result.stderr)
    if result.returncode != 0:
        print("[warn] no se pudo correr 'memanto connect codex' (no bloqueante)")
        return
    print("[ok] AGENTS.md + .agents/skills/memanto/ listos para Codex CLI")


def sync_memory_snapshot() -> None:
    """Refresh the committed MEMORY.md snapshot from the active agent."""
    result = _run(["memanto", "memory", "sync", "--project-dir", str(PROJECT_ROOT)])
    print(result.stdout + result.stderr)
    if result.returncode != 0:
        print("[warn] no se pudo correr 'memanto memory sync' (no bloqueante)")
        return
    print("[ok] MEMORY.md sincronizado")


def main() -> None:
    ensure_memanto_installed()
    configure_backend()
    configure_onprem_state()
    create_or_activate_agent()
    connect_codex()
    sync_memory_snapshot()
    print()
    print("Listo. Prueba con:")
    print('  memanto remember "..." --type fact --confidence 1.0 '
          '--provenance explicit_statement --source claude-code')
    print('  memanto recall "..."')
    print('  memanto answer "..."')


if __name__ == "__main__":
    main()
