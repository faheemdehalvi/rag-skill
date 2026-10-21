# /rag skill

A Claude Code skill for multimodal RAG over local documents, using [HKUDS RAG-Anything](https://github.com/HKUDS/RAG-Anything) with a LightRAG knowledge graph and MinerU parsing. It ingests PDFs, Office files, images, text and markdown into a named knowledge base, then answers questions across text, tables, figures and equations. By default it runs on Ollama on your own machine. Nothing leaves the machine unless you set `RAG_PROVIDER=openai`.

## Prerequisites

| Need | Version | Install |
| --- | --- | --- |
| Python | 3.11 (the tested version) | `brew install python@3.11` |
| Ollama | any recent release | `brew install ollama`, then `ollama serve` |
| Ollama models | `llama3.2` (answers), `nomic-embed-text` (embeddings) | `ollama pull llama3.2 && ollama pull nomic-embed-text` |
| LibreOffice | only for Office files | `brew install --cask libreoffice` |
| Vision model | optional; without one, images are skipped | e.g. `ollama pull llava`, then set `RAG_VISION_MODEL=llava` when you create the knowledge base |

## Install

```sh
git clone https://github.com/faheemdehalvi/rag-skill.git ~/.claude/skills/rag
~/.claude/skills/rag/scripts/setup.sh
```

`setup.sh` creates an isolated venv at `~/.rag/venv` and installs `requirements.txt`. It touches nothing outside `~/.rag` and is safe to re-run. To do the same by hand:

```sh
python3.11 -m venv ~/.rag/venv
~/.rag/venv/bin/python -m pip install --upgrade pip
~/.rag/venv/bin/python -m pip install -r ~/.claude/skills/rag/requirements.txt
```

The first PDF or image ingest downloads MinerU's models, which takes a while.

## Use

In Claude Code, type `/rag` followed by what you want, e.g. `/rag ingest contracts ~/Documents/contracts` or `/rag contracts what are the notice periods?`. `SKILL.md` has the full routing.

## Settings

| Variable | Default |
| --- | --- |
| `RAG_HOME` | `~/.rag` |
| `RAG_PROVIDER` | `ollama` (or `openai`) |
| `OLLAMA_HOST` | `http://localhost:11434` |
| `RAG_LLM_MODEL` | `llama3.2` (openai: `gpt-4o-mini`) |
| `RAG_VISION_MODEL` | none (openai: `gpt-4o`) |
| `RAG_EMBED_MODEL` / `RAG_EMBED_DIM` | `nomic-embed-text` / 768 (openai: `text-embedding-3-large` / 3072) |
| `RAG_API_KEY` or `OPENAI_API_KEY` | needed only for `openai` |

Each knowledge base records its embedding model when it is created. Vectors from a different embedding model can't be compared, so keep the same one for that base.
