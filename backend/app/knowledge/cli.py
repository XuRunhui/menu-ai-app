"""Build and inspect the knowledge base.

Examples (run from backend/):
    python -m app.knowledge.cli build                      # notes + FlavorGraph + Wikidata + Wikipedia + cookbook
    python -m app.knowledge.cli ingest-pdf book.pdf --title "My Cookbook" --license "Personal use"
    python -m app.knowledge.cli extract-graph --document-id 1 --limit 20   # uses DeepSeek (costs tokens)
    python -m app.knowledge.cli stats
    python -m app.knowledge.cli search "how to make a cream sauce"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.core.config import settings
from app.knowledge.db import init_knowledge_db, knowledge_session

DEFAULT_GUTENBERG_BOOK = 65061  # The Boston Cooking-School Cook Book (Fannie Merritt Farmer, 1896)


def _llm_client(required: bool):
    if not settings.deepseek_api_key:
        if required:
            sys.exit("DEEPSEEK_API_KEY is not set")
        return None
    from app.services.llm_client import LLMClient

    return LLMClient(api_key=settings.deepseek_api_key)


def cmd_build(args) -> None:
    from app.knowledge.sources import documents, flavorgraph, wikidata, wikipedia

    steps = [("Meal composition notes", lambda db: documents.import_editorial(db))]
    if not args.skip_flavorgraph:
        steps.append(("FlavorGraph", lambda db: flavorgraph.import_flavorgraph(db, *flavorgraph.fetch())))
    if not args.skip_wikidata:
        steps.append(("Wikidata", lambda db: wikidata.import_wikidata(db, wikidata.fetch())))
    if not args.skip_wikipedia:
        steps.append(("Wikipedia meal structures", lambda db: wikipedia.import_wikipedia(db)))
    if not args.skip_gutenberg:
        steps.append((
            f"Gutenberg #{args.gutenberg_id}",
            lambda db: documents.import_gutenberg(db, args.gutenberg_id, documents.fetch_gutenberg(args.gutenberg_id)),
        ))

    failures = 0
    for name, step in steps:
        try:
            with knowledge_session() as db:
                print(f"{name}: {step(db)}")
        except Exception as exc:  # keep going so one unavailable source doesn't block the rest
            failures += 1
            print(f"{name}: FAILED ({exc})", file=sys.stderr)
    cmd_stats(args)
    if failures and args.strict:
        sys.exit(1)


def cmd_ingest_pdf(args) -> None:
    from app.knowledge.sources.documents import import_pdf

    with knowledge_session() as db:
        result = import_pdf(
            db, Path(args.path), args.title, args.license, url=args.url,
            llm_client=_llm_client(required=False) if args.ocr else None, replace=args.replace,
        )
    print(result)


def cmd_ingest_text(args) -> None:
    from app.knowledge.sources.documents import import_text_file

    with knowledge_session() as db:
        print(import_text_file(db, Path(args.path), args.title, args.license, url=args.url, replace=args.replace))


def cmd_extract_graph(args) -> None:
    from app.knowledge.extraction import extract_graph

    with knowledge_session() as db:
        print(extract_graph(db, _llm_client(required=True), args.document_id, args.limit))


def cmd_stats(_args) -> None:
    from app.knowledge.models import Document
    from app.knowledge.store import stats
    from sqlalchemy import select

    with knowledge_session() as db:
        print(json.dumps(stats(db), indent=2))
        for doc in db.scalars(select(Document)):
            print(f"  document {doc.id}: {doc.title} [{doc.source}, {doc.license}]")


def cmd_search(args) -> None:
    from app.knowledge.retrieval import search_passages

    with knowledge_session() as db:
        for hit in search_passages(db, args.query, top_k=args.top_k):
            print(f"\n[{hit['score']}] {hit['document_title']} (page {hit['page']})\n{hit['text'][:400]}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.knowledge.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Download and import the default sources")
    build.add_argument("--gutenberg-id", type=int, default=DEFAULT_GUTENBERG_BOOK)
    build.add_argument("--skip-flavorgraph", action="store_true")
    build.add_argument("--skip-wikidata", action="store_true")
    build.add_argument("--skip-gutenberg", action="store_true")
    build.add_argument("--skip-wikipedia", action="store_true")
    build.add_argument("--strict", action="store_true", help="Exit non-zero if any source fails")
    build.set_defaults(func=cmd_build)

    for name, func, helptext in (("ingest-pdf", cmd_ingest_pdf, "Import a PDF"), ("ingest-text", cmd_ingest_text, "Import a .txt/.md file")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("path")
        p.add_argument("--title", required=True)
        p.add_argument("--license", required=True, help='e.g. "Public domain", "CC BY-SA 4.0", "Personal use only"')
        p.add_argument("--url", default="")
        p.add_argument("--replace", action="store_true", help="Re-import if already present")
        if name == "ingest-pdf":
            p.add_argument("--ocr", action="store_true", help="OCR pages without a text layer using DeepSeek vision")
        p.set_defaults(func=func)

    extract = sub.add_parser("extract-graph", help="Extract graph edges from a document with DeepSeek")
    extract.add_argument("--document-id", type=int, required=True)
    extract.add_argument("--limit", type=int, default=20, help="Max passages to process this run")
    extract.set_defaults(func=cmd_extract_graph)

    sub.add_parser("stats", help="Show counts").set_defaults(func=cmd_stats)

    search = sub.add_parser("search", help="Semantic search over imported passages")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.set_defaults(func=cmd_search)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_knowledge_db()
    args.func(args)


if __name__ == "__main__":
    main()
