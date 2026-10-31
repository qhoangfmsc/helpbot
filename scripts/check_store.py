"""Re-check what the store holds against the Markdown files in articles/ (read-only, no uploads).

Usage: python scripts/check_store.py [--brief]     (--brief prints only the statistics, not one entry per article)
Prints store statistics, local statistics and, per article: id, status, title, link, size, estimated chunks, content hash.
Exit code 0 when the store matches articles/, 1 when something is missing, outdated or extra (fix: python scripts/sync_docs.py),
2 for a missing/invalid key or settings, 3 when Gemini is unreachable, timed out or the quota is used up (each prints its own message).
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from helpbot.chunking import MAX_TOKENS_PER_CHUNK, OVERLAP_TOKENS  # noqa: E402
from helpbot.pipeline import LocalDoc, load_local  # noqa: E402
from helpbot.problems import EXIT_API, EXIT_CONFIG, classify, explain  # noqa: E402
from helpbot.settings import load_settings  # noqa: E402
from helpbot.store import FileSearchStore, make_client  # noqa: E402
from helpbot.sync import RemoteDoc, plan_delta  # noqa: E402

STATUS = {"in_sync": "in sync", "missing": "MISSING in store", "outdated": "OUTDATED in store"}


def build_report(local: dict[str, LocalDoc], remote: list[RemoteDoc]) -> dict[str, list[str]]:
    """Article ids per status. `missing`/`outdated` need an upload, `extra` is in the store but not in articles/."""
    delta = plan_delta({i: d.hash for i, d in local.items()}, remote)
    return {
        "in_sync": delta.skipped,
        "missing": delta.added,
        "outdated": delta.updated,
        "extra": sorted({d.article_id for d in delta.orphans}, key=int),
        "duplicates": sorted({d.article_id for d in delta.duplicates}, key=int),
    }


def is_different(report: dict[str, list[str]]) -> bool:
    return any(report[k] for k in ("missing", "outdated", "extra", "duplicates"))


def article_info(path: Path) -> tuple[str, str]:
    """Title and `Article URL:` from the first lines of a converted article."""
    text = path.read_text(encoding="utf-8")
    title = re.match(r"# (.+)", text)
    url = re.search(r"^Article URL: (\S+)$", text, re.M)
    return (title.group(1) if title else "(no title)"), (url.group(1) if url else "(no Article URL line)")


def format_local_stats(local: dict[str, LocalDoc]) -> str:
    sizes = [d.path.stat().st_size for d in local.values()] or [0]
    chunks = sum(d.chunks for d in local.values())
    return (
        f"local  : {len(local)} files in articles/ | {sum(sizes) / 1024:.0f} KB total, avg {sum(sizes) / len(sizes) / 1024:.1f} KB "
        f"(smallest {min(sizes) / 1024:.1f}, largest {max(sizes) / 1024:.1f}) | ~{chunks} chunks estimated "
        f"({MAX_TOKENS_PER_CHUNK} tokens per chunk, {OVERLAP_TOKENS} overlap)"
    )


def format_counts(report: dict[str, list[str]]) -> str:
    return (
        f"compare: in sync {len(report['in_sync'])} | missing in store {len(report['missing'])} | outdated in store {len(report['outdated'])} "
        f"| extra in store {len(report['extra'])} | duplicates {len(report['duplicates'])}"
    )


def format_articles(local: dict[str, LocalDoc], remote: list[RemoteDoc], report: dict[str, list[str]]) -> str:
    """One entry per article (two lines: facts, then the link) plus the documents that have no file."""
    status = {i: STATUS["in_sync"] for i in report["in_sync"]}
    status.update({i: STATUS["missing"] for i in report["missing"]})
    status.update({i: STATUS["outdated"] for i in report["outdated"]})
    store_hash = {d.article_id: d.content_hash for d in remote}
    lines = []
    for n, article_id in enumerate(sorted(local, key=int), 1):
        doc = local[article_id]
        title, url = article_info(doc.path)
        in_store = store_hash.get(article_id)
        hash_note = f"hash {doc.hash[:8]}" + (f" (store has {in_store[:8]})" if in_store and in_store != doc.hash else "")
        lines.append(f"{n:>3}. {article_id:<15} {status[article_id]:<18} {doc.path.stat().st_size / 1024:>5.1f} KB  ~{doc.chunks} chunks  {hash_note}")
        lines.append(f"     {title}")
        lines.append(f"     {url}")
    for article_id in report["extra"]:
        names = ", ".join(d.name.rsplit("/", 1)[-1] for d in remote if d.article_id == article_id)
        lines.append(f"  +  {article_id:<15} {'EXTRA in store':<18} no file in articles/ (store document: {names})")
    for article_id in report["duplicates"]:
        lines.append(f"  !  {article_id:<15} {'DUPLICATE in store':<18} more than one document for this article")
    return "\n".join(lines)


def main() -> int:
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY is not set (copy .env.sample to .env and put your key in it)", file=sys.stderr)
        return EXIT_CONFIG
    try:
        settings = load_settings()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_CONFIG
    files = {p.name.split("-")[0]: p for p in sorted(settings.path(settings.articles_dir).glob("*.md"))}
    if not files:
        print("error: no Markdown files in articles/ (run `python scripts/sync_docs.py` first)", file=sys.stderr)
        return EXIT_CONFIG
    try:
        client = make_client(api_key, settings.request_timeout_seconds)
        store = FileSearchStore.open(client, settings.store_name)
        info = client.file_search_stores.get(name=store.name)
        local, remote = load_local(files), store.list_documents()
    except Exception as error:
        print(f"error: could not read the store. {explain(error)}", file=sys.stderr)
        return EXIT_CONFIG if classify(error) == "auth" else EXIT_API

    report = build_report(local, remote)
    print(
        f"store  : {info.display_name} ({store.name})\n"
        f"         {info.active_documents_count} active documents, {getattr(info, 'pending_documents_count', 0) or 0} pending, "
        f"{getattr(info, 'failed_documents_count', 0) or 0} failed | {(info.size_bytes or 0) / 1024:.0f} KB | "
        f"embedding model {getattr(info, 'embedding_model', None) or 'unknown'}"
    )
    print(format_local_stats(local))
    print(format_counts(report))
    if "--brief" not in sys.argv:
        print("\n" + format_articles(local, remote, report) + "\n")
    if not is_different(report):
        print("OK: the store matches articles/.")
        return 0
    print("DIFFERENT: run `python scripts/sync_docs.py` to upload missing/outdated documents and remove extras.")
    if len(report["extra"]) > len(local):
        print("Note: more than half of the store is extra, so sync_docs refuses to delete it by default; "
              "if that is intended run once: python scripts/sync_docs.py --allow-mass-delete")
    return 1


if __name__ == "__main__":
    sys.exit(main())
