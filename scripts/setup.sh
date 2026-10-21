#!/bin/zsh
# Create or refresh the isolated RAG-Anything environment at ~/.rag/venv.
# Touches nothing outside ~/.rag. Safe to re-run.
set -eu
RAG_HOME="${RAG_HOME:-$HOME/.rag}"
PY="${RAG_PYTHON:-/opt/homebrew/bin/python3.11}"
mkdir -p "$RAG_HOME/kb"
[ -x "$RAG_HOME/venv/bin/python" ] || "$PY" -m venv "$RAG_HOME/venv"
"$RAG_HOME/venv/bin/python" -m pip install -q --upgrade pip
# Pinned versions live in requirements.txt (MinerU must stay below 4).
"$RAG_HOME/venv/bin/python" -m pip install -q -r "$(dirname "$0")/../requirements.txt"
"$RAG_HOME/venv/bin/python" -c "import raganything, lightrag; print('raganything', raganything.__version__)"
"$RAG_HOME/venv/bin/mineru" --version || echo "mineru CLI missing"
