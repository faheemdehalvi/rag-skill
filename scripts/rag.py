#!/usr/bin/env python3
"""Multimodal RAG over local documents, backed by HKUDS/RAG-Anything.

Knowledge bases live in $RAG_HOME/kb/<name> (default ~/.rag/kb). Each KB pins
its provider and embedding model in kb.json at creation, because vectors from
a different embedding model are not comparable.

Usage:
  rag.py ingest <kb> <file-or-folder>... [--parser mineru|docling] [--method auto|ocr|txt]
  rag.py query  <kb> "question" [--mode mix|hybrid|local|global|naive] [--context]
  rag.py list
  rag.py status <kb>
  rag.py doctor
"""
import argparse
import asyncio
import json
import os
import pathlib
import sys

RAG_HOME = pathlib.Path(os.environ.get("RAG_HOME", pathlib.Path.home() / ".rag"))
KB_ROOT = RAG_HOME / "kb"
TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
# RAG-Anything shells out to `mineru` via PATH; expose this venv's console scripts.
os.environ["PATH"] = str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")


def provider_from_env():
    """Provider settings for a new KB. Existing KBs use their pinned kb.json."""
    provider = os.environ.get("RAG_PROVIDER", "ollama")
    if provider == "ollama":
        return {
            "provider": "ollama",
            "host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            "llm_model": os.environ.get("RAG_LLM_MODEL", "llama3.2"),
            "vision_model": os.environ.get("RAG_VISION_MODEL"),
            "embed_model": os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text"),
            "embed_dim": int(os.environ.get("RAG_EMBED_DIM", "768")),
        }
    if provider == "openai":
        return {
            "provider": "openai",
            "base_url": os.environ.get("RAG_BASE_URL"),
            "llm_model": os.environ.get("RAG_LLM_MODEL", "gpt-4o-mini"),
            "vision_model": os.environ.get("RAG_VISION_MODEL", "gpt-4o"),
            "embed_model": os.environ.get("RAG_EMBED_MODEL", "text-embedding-3-large"),
            "embed_dim": int(os.environ.get("RAG_EMBED_DIM", "3072")),
        }
    sys.exit(f"Unknown RAG_PROVIDER {provider!r}; use ollama or openai")


def kb_settings(name, create):
    kb = KB_ROOT / name
    meta = kb / "kb.json"
    if meta.exists():
        return kb, json.loads(meta.read_text())
    if not create:
        sys.exit(f"No knowledge base {name!r}. Known: {', '.join(list_kbs()) or 'none'}")
    settings = provider_from_env()
    kb.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(settings, indent=2) + "\n")
    return kb, settings


def list_kbs():
    return sorted(p.parent.name for p in KB_ROOT.glob("*/kb.json"))


def api_key(settings):
    if settings["provider"] == "ollama":
        return "ollama"  # Ollama ignores the key; the client requires one.
    key = os.environ.get("RAG_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("Set RAG_API_KEY or OPENAI_API_KEY for the openai provider")
    return key


def build(kb, settings, parser="mineru", method="auto"):
    import numpy as np
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc
    from raganything import RAGAnything, RAGAnythingConfig

    key = api_key(settings)
    base_url = (settings["host"] + "/v1") if settings["provider"] == "ollama" else settings.get("base_url")

    async def llm(prompt, system_prompt=None, history_messages=None, **kwargs):
        return await openai_complete_if_cache(
            settings["llm_model"], prompt, system_prompt=system_prompt,
            history_messages=history_messages or [], api_key=key, base_url=base_url, **kwargs)

    vision = None
    if settings.get("vision_model"):
        async def vision(prompt, system_prompt=None, history_messages=None,
                         image_data=None, messages=None, **kwargs):
            if messages is None and image_data:
                messages = [m for m in [
                    {"role": "system", "content": system_prompt} if system_prompt else None,
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    ]},
                ] if m]
            if messages is None:
                return await llm(prompt, system_prompt, history_messages, **kwargs)
            return await openai_complete_if_cache(
                settings["vision_model"], "", system_prompt=None, history_messages=[],
                messages=messages, api_key=key, base_url=base_url, **kwargs)

    if settings["provider"] == "ollama":
        async def embed(texts):
            import ollama
            response = await ollama.AsyncClient(host=settings["host"]).embed(
                model=settings["embed_model"], input=texts)
            return np.array(response.embeddings)  # LightRAG requires an ndarray.
    else:
        from functools import partial
        embed = partial(openai_embed.func, model=settings["embed_model"], api_key=key, base_url=base_url)

    config = RAGAnythingConfig(
        working_dir=str(kb / "storage"),
        parser=parser,
        parse_method=method,
        enable_image_processing=vision is not None,
        enable_table_processing=True,
        enable_equation_processing=True,
    )
    return RAGAnything(
        config=config, llm_model_func=llm, vision_model_func=vision,
        embedding_func=EmbeddingFunc(embedding_dim=settings["embed_dim"], max_token_size=8192, func=embed),
    )


async def ingest(args):
    kb, settings = kb_settings(args.kb, create=True)
    rag = build(kb, settings, args.parser, args.method)
    output = str(kb / "parsed")
    done, failed = [], []
    try:
        for raw in args.paths:
            path = pathlib.Path(raw).expanduser().resolve()
            try:
                if path.is_dir():
                    await rag.process_folder_complete(str(path), output_dir=output, recursive=True)
                elif path.suffix.lower() in TEXT_SUFFIXES:
                    # Plain text needs no layout parsing; skip the PDF round trip.
                    await rag.insert_content_list(
                        [{"type": "text", "text": path.read_text(errors="replace"), "page_idx": 0}],
                        file_path=str(path))
                else:
                    await rag.process_document_complete(str(path), output_dir=output)
                done.append(str(path))
            except Exception as error:  # Report and keep going with the other inputs.
                failed.append((str(path), f"{type(error).__name__}: {error}"))
    finally:
        await rag.finalize_storages()
    print(json.dumps({"kb": args.kb, "ingested": done, "failed": failed}, indent=2))
    return 1 if failed else 0


async def query(args):
    kb, settings = kb_settings(args.kb, create=False)
    rag = build(kb, settings)
    try:
        init = await rag._ensure_lightrag_initialized()
        if isinstance(init, dict) and not init.get("success", True):
            sys.exit(init.get("error", "LightRAG failed to initialise"))
        kwargs = {"enable_rerank": False}  # No rerank model is configured.
        if args.context:
            kwargs["only_need_context"] = True
        answer = await rag.aquery(args.question, mode=args.mode, **kwargs)
    finally:
        await rag.finalize_storages()
    if not answer:
        print("Query failed or returned nothing; see the log above.", file=sys.stderr)
        return 1
    print(answer)
    return 0


def status(args):
    kb, settings = kb_settings(args.kb, create=False)
    docs = {}
    status_file = kb / "storage" / "kv_store_doc_status.json"
    if status_file.exists():
        for doc in json.loads(status_file.read_text()).values():
            state = doc.get("status", "unknown")
            docs[state] = docs.get(state, 0) + 1
    print(json.dumps({"kb": args.kb, "path": str(kb), "settings": settings, "documents": docs}, indent=2))
    return 0


def doctor(_):
    checks = {}
    try:
        import raganything
        checks["raganything"] = raganything.__version__
    except ImportError as error:
        checks["raganything"] = f"missing ({error}); run scripts/setup.sh"
    mineru = pathlib.Path(sys.executable).parent / "mineru"
    checks["mineru"] = "present" if mineru.exists() else "missing"
    try:
        import ollama
        settings = provider_from_env()
        if settings["provider"] == "ollama":
            names = [m.model for m in ollama.Client(host=settings["host"]).list().models]
            for model in (settings["llm_model"], settings["embed_model"]):
                checks[f"ollama:{model}"] = "present" if any(n.split(":")[0] == model.split(":")[0] for n in names) else f"missing; ollama pull {model}"
    except Exception as error:
        checks["ollama"] = f"unreachable ({type(error).__name__}: {error})"
    checks["libreoffice"] = "present" if any(
        pathlib.Path(p, "soffice").exists() for p in os.environ.get("PATH", "").split(":")) else "missing (needed for Office files)"
    checks["knowledge_bases"] = list_kbs()
    print(json.dumps(checks, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("kb")
    p.add_argument("paths", nargs="+")
    p.add_argument("--parser", default="mineru", choices=["mineru", "docling", "paddleocr"])
    p.add_argument("--method", default="auto", choices=["auto", "ocr", "txt"])
    p = sub.add_parser("query")
    p.add_argument("kb")
    p.add_argument("question")
    p.add_argument("--mode", default="mix", choices=["mix", "hybrid", "local", "global", "naive"])
    p.add_argument("--context", action="store_true", help="return retrieved context only, no LLM answer")
    sub.add_parser("list")
    p = sub.add_parser("status")
    p.add_argument("kb")
    sub.add_parser("doctor")
    args = parser.parse_args()

    if args.command == "list":
        print("\n".join(list_kbs()) or "(no knowledge bases)")
        return 0
    if args.command == "status":
        return status(args)
    if args.command == "doctor":
        return doctor(args)
    return asyncio.run(ingest(args) if args.command == "ingest" else query(args))


if __name__ == "__main__":
    sys.exit(main())
