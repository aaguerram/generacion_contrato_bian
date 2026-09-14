#!/usr/bin/env bash
# Ejecuta `graphify` (github.com/Graphify-Labs/graphify, paquete PyPI `graphifyy`)
# contra el servidor Ollama on-prem de Produbanco -- el mismo host que usa MEMANTO
# (ver scripts/setup_memanto.py) y que ya usa este proyecto para failover LLM/
# embeddings (ver config.yaml -> providers.ollama).
#
# No va en .env: .env es solo API keys de este proyecto (ver CLAUDE.md); esto es
# config de una herramienta de desarrollo aparte, no del pipeline de mapeo BIAN.
#
# OLLAMA_BASE_URL se usa TAL CUAL por graphify cuando está seteada explícitamente
# (no le agrega /v1 sola -- eso solo pasa si en cambio se usa OLLAMA_HOST) --
# por eso el /v1 va aquí explícito, igual que en config.yaml.
#
# Ese servidor solo expone un modelo de chat (`qwen3.8:27b-q8_0`); el otro
# modelo que tiene, `qwen3-embedding:8b`, es de solo-embeddings y graphify no
# usa embeddings en ningún punto (ver README: "No embeddings, no vector store").
#
# Uso:
#   scripts/graphify-ollama.sh extract .
#   scripts/graphify-ollama.sh update .
#   scripts/graphify-ollama.sh query "..."
#
# BLINDAJE: este proyecto ahora tiene GOOGLE_API_KEY en .env (para su propio
# failover LLM). graphify revisa GEMINI_API_KEY *o* GOOGLE_API_KEY y prueba
# backends en este orden: gemini -> kimi -> claude -> openai -> deepseek ->
# azure -> bedrock -> ollama (ollama va ULTIMO, es opt-in). Si alguna vez esta
# GOOGLE_API_KEY exportada en la shell que invoca esto (p.ej. tras un `source
# .env` para probar el CLI de este proyecto), graphify elegiria Gemini en vez
# de Ollama sin avisar -- el propio código de graphify tiene un comentario
# advirtiendo justo este escenario. Dos capas para que eso sea imposible aquí:
#   1. `unset` de toda key de otro backend, en ESTE proceso (nunca toca la
#      shell que llama al script -- unset/export aquí no se propaga hacia
#      afuera; ver `help bash` -> "Shell Builtin Commands").
#   2. `--backend ollama` forzado al FINAL de los argumentos, SOLO para los
#      subcomandos que de verdad llaman a un LLM (extract, cluster-only,
#      label). `update`/`query`/`path`/`explain`/etc. no reconocen --backend
#      -- graphify aborta con "error: unknown option" si se lo mandamos
#      igual (bug real, encontrado corriendo esto la primera vez), así que
#      el forzado va detrás de un `case` sobre el subcomando ($1).
#
# --max-concurrency 1: el server Ollama es una sola instancia (sin paralelismo
# real) sirviendo un modelo "thinking" de 27B lento -- con el default (4) los
# requests compiten entre sí y todos terminan en APITimeoutError (visto en
# producción: 23/27 docs descartados). extract no lo auto-fuerza (su --help
# solo lo "sugiere"); cluster-only/label sí lo auto-fuerzan para ollama, pero
# pasarlo explícito ahí no hace daño.

unset GEMINI_API_KEY GOOGLE_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY \
      MOONSHOT_API_KEY DEEPSEEK_API_KEY AZURE_OPENAI_API_KEY \
      AZURE_OPENAI_ENDPOINT AWS_PROFILE AWS_REGION AWS_DEFAULT_REGION

export OLLAMA_BASE_URL="http://100.102.221.79:11434/v1"
export OLLAMA_MODEL="qwen3.8:27b-q8_0"
# Cualquier valor no vacío alcanza -- el servidor no exige autenticación real,
# pero graphify emite un warning si OLLAMA_API_KEY queda sin definir.
export OLLAMA_API_KEY="${OLLAMA_API_KEY:-not-needed}"

case "$1" in
  extract|cluster-only|label)
    exec graphify "$@" --backend ollama --max-concurrency 1
    ;;
  *)
    exec graphify "$@"
    ;;
esac
