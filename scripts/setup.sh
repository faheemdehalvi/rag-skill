#!/bin/zsh
# Create or refresh the isolated RAG-Anything environment at ~/.rag/venv.
# Touches nothing outside ~/.rag. Safe to re-run.
set -eu
RAG_HOME="${RAG_HOME:-$HOME/.rag}"
PY="${RAG_PYTHON:-/opt/homebrew/bin/python3.11}"
mkdir -p "$RAG_HOME/kb"
[ -x "$RAG_HOME/venv/bin/python" ] || "$PY" -m venv "$RAG_HOME/venv"
"$RAG_HOME/venv/bin/python" -m pip install -q --upgrade pip
# MinerU 4 replaced the `mineru -p/-o/-m` CLI that raganything 1.4.x invokes.
"$RAG_HOME/venv/bin/python" -m pip install -q 'raganything[image,text]' 'mineru[core]>=3.4.1,<4' ollama python-dotenv
"$RAG_HOME/venv/bin/python" -c "import raganything, lightrag; print('raganything', raganything.__version__)"
"$RAG_HOME/venv/bin/mineru" --version || echo "mineru CLI missing"
