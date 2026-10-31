"""Re-check what the store holds against the Markdown files in articles/ (read-only, no uploads).

Usage: python scripts/check_store.py [--list]     --list prints every article and its status
Exit code 0 when the store matches articles/, 1 when something is missing, outdated or extra (fix: python scripts/sync_docs.py).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from helpbot.pipeline import LocalDoc, load_local  # noqa: E402
from helpbot.store import DEFAULT_STORE_NAME, FileSearchStore  # noqa: E402
from helpbot.sync import RemoteDoc, plan_delta  # noqa: E402


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


def format_report(report: dict[str, list[str]], local: dict[str, LocalDoc], listing: bool) -> str:
    lines = [
        f"in sync: {len(report['in_sync'])} | missing in store: {len(report['missing'])} | outdated in store: {len(report['outdated'])} "
        f"| extra in store: {len(report['extra'])} | duplicates: {len(report['duplicates'])}"
    ]
    if listing:
        status = {i: "in sync" for i in report["in_sync"]}
        status.update({i: "MISSING in store" for i in report["missing"]})
        status.update({i: "OUTDATED in store" for i in report["outdated"]})
        lines += [f"  {i:<16} {status[i]:<18} {local[i].path.name}" for i in sorted(status, key=int)]
        lines += [f"  {i:<16} {'EXTRA in store':<18} (no file in articles/)" for i in report["extra"]]
    elif any(report[k] for k in ("missing", "outdated", "extra", "duplicates")):
        for key in ("missing", "outdated", "extra", "duplicates"):
            if report[key]:
                lines.append(f"  {key}: {', '.join(report[key])}")
    return "\n".join(lines)


def main() -> int:
    load_dotenv(ROOT / ".env")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    store = FileSearchStore.open(client, os.environ.get("GEMINI_FILE_SEARCH_STORE", DEFAULT_STORE_NAME))
    info = client.file_search_stores.get(name=store.name)
    files = {p.name.split("-")[0]: p for p in sorted((ROOT / os.environ.get("ARTICLES_DIR", "articles")).glob("*.md"))}
    local, remote = load_local(files), store.list_documents()

    print(f"store: {info.display_name} ({store.name}) | documents in store: {info.active_documents_count} | size: {(info.size_bytes or 0) / 1024:.0f} KB")
    print(f"local files: {len(local)} in articles/")
    report = build_report(local, remote)
    print(format_report(report, local, "--list" in sys.argv))
    if all(not report[k] for k in ("missing", "outdated", "extra", "duplicates")):
        print("OK: the store matches articles/.")
        return 0
    print("DIFFERENT: run `python scripts/sync_docs.py` to fix missing/outdated/extra documents.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
