---
name: rag
description: Multimodal RAG over local documents using HKUDS RAG-Anything (LightRAG knowledge graph + MinerU parsing). Ingest PDFs, Office files, images, text and markdown into a named knowledge base, then ask questions that span text, tables, figures and equations. Triggers on /rag, "rag this", "build a knowledge base from", "ingest these documents", "ask my documents", "query the <name> kb". Runs locally on Ollama by default; nothing leaves the machine unless RAG_PROVIDER=openai.
---

# /rag

Wraps [HKUDS/RAG-Anything](https://github.com/HKUDS/RAG-Anything) behind one CLI.
Documents are parsed (MinerU by default), split into text, images, tables and
equations, and indexed into a LightRAG knowledge graph plus vector store.

```
RAG=~/.rag/venv/bin/python
CLI=~/.claude/skills/rag/scripts/rag.py
```

## Routing

Parse the message after `/rag`:

| User says | Run |
|---|---|
| `/rag ingest <kb> <paths…>` or "add these files to <kb>" | `$RAG $CLI ingest <kb> <paths…>` |
| `/rag <kb> <question>` or "ask <kb> …" | `$RAG $CLI query <kb> "<question>" --context`, then answer from the context |
| `/rag list` | `$RAG $CLI list` |
| `/rag status <kb>` | `$RAG $CLI status <kb>` |
| `/rag doctor` or a failure | `$RAG $CLI doctor` |

No KB named and only one exists: use it. Several exist: ask which. No path or
question given: ask for it. Do not invent a target.

## Answering questions

Default to `--context`: it returns the retrieved entities, relations and chunks
without an LLM answer, and you answer from that. You are a stronger reader than
the default local model (llama3.2, 3B), and it is cheaper than a second LLM
pass. Cite the source file paths that appear in the context. If the context
does not contain the answer, say so. Do not fill the gap from general knowledge
without labelling it.

Drop `--context` only when the user explicitly wants RAG-Anything's own answer.

Modes: `mix` (default, graph + vector), `hybrid` (local + global graph),
`local` (entity-centric), `global` (relationship and theme-centric), `naive`
(plain vector search). Use `global` for "what are the themes / overall"
questions, `local` for questions about a specific named thing.

## Ingest

- Folders are walked recursively. `.txt`/`.md` are inserted directly as text,
  with no PDF conversion.
- PDFs and images go through MinerU. The first run downloads its models, which takes a while.
  `--method ocr` for scanned PDFs, `--method txt` for born-digital text PDFs (faster).
- Office files need LibreOffice (installed at `/opt/homebrew/bin/soffice`).
- Entity extraction calls the LLM per chunk. On local llama3.2 a long PDF takes
  minutes. Run large ingests with `run_in_background` and report when done.
- Output is JSON: `ingested` and `failed` lists. Report failures with their
  reason. Never say a file was ingested if it appears in `failed`.

## Providers

Each KB pins its provider and embedding model in `~/.rag/kb/<kb>/kb.json` on
first ingest. Changing env vars later does not affect an existing KB. To
switch embedding models, make a new KB.

- **ollama** (default): `llama3.2` + `nomic-embed-text` (768-dim), local.
  Images are skipped unless `RAG_VISION_MODEL` names a vision model
  (e.g. `llava`, `qwen2.5vl`), set when the KB is created.
- **openai**: `RAG_PROVIDER=openai` plus `RAG_API_KEY` (or `OPENAI_API_KEY`).
  `RAG_BASE_URL` points at any OpenAI-compatible endpoint (OpenRouter, LM Studio, vLLM).
  Defaults `gpt-4o-mini` / `gpt-4o` / `text-embedding-3-large` (3072-dim).
  Sends document content to that provider. Confirm with the user before
  creating a KB this way from client or personal documents.

Overrides: `RAG_LLM_MODEL`, `RAG_VISION_MODEL`, `RAG_EMBED_MODEL`, `RAG_EMBED_DIM`,
`OLLAMA_HOST`, `RAG_HOME` (default `~/.rag`).

## Setup

`~/.claude/skills/rag/scripts/setup.sh` creates `~/.rag/venv` (Python 3.11) and
installs `raganything[image,text]` + `ollama`. It touches nothing outside `~/.rag`.
Re-run it to repair. `doctor` reports what is missing.

## Limits

- Deleting a KB means removing `~/.rag/kb/<kb>`. Confirm before deleting.
- Re-ingesting the same file is deduplicated by content hash. Edited files are
  added as new documents. Old versions are not removed.
- `pip install raganything` pins `lightrag-hku<1.5`. Do not upgrade LightRAG
  in this venv.
