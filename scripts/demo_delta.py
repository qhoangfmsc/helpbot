"""Live demo of the delta rule on a throwaway store: existing articles are skipped, only new/edited ones upload.

Usage: python scripts/demo_delta.py [--keep]     (uses the real API: ~40 uploads, deletes the store afterwards)
Scenarios use the newest-N window (ARTICLE_LIMIT): 30 -> same -> 40 -> a brand-new article -> an edited article.
"""

import dataclasses
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helpbot.pipeline import run_job  # noqa: E402
from helpbot.store import FileSearchStore  # noqa: E402
from helpbot.zendesk import Article, fetch_articles  # noqa: E402

STORE_NAME = "helpbot-demo"


def main() -> int:
    load_dotenv()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    store = FileSearchStore.open(client, STORE_NAME)
    live = sorted(fetch_articles(), key=lambda a: (a.updated_at, int(a.id)), reverse=True)
    newest = live[0]
    new_article = Article("999999999999", "Demo: brand-new article", "https://example.invalid/demo", "2999-01-01T00:00:00Z", "<p>Just published.</p>")
    edited = [dataclasses.replace(newest, body_html=newest.body_html + "<p>Edited after the first run.</p>")] + live[1:]
    out = Path(tempfile.mkdtemp())

    scenarios = [  # (what happens, articles seen by the job, ARTICLE_LIMIT, expected (added, updated, skipped))
        ("first run, 30 newest", live, 30, (30, 0, 0)),
        ("same again (nothing changed)", live, 30, (0, 0, 30)),
        ("window widened to 40 (10 older, not yet uploaded)", live, 40, (10, 0, 30)),
        ("a brand-new article appears", live + [new_article], 40, (1, 0, 39)),
        ("the newest article is edited", edited + [new_article], 40, (0, 1, 39)),
    ]
    failures = 0
    for label, articles, limit, expected in scenarios:
        summary = run_job(articles, out, store, workers=4, limit=limit)
        actual = (summary.added, summary.updated, summary.skipped)
        verdict = "OK  " if actual == expected else "FAIL"
        failures += actual != expected
        print(f"{verdict} {label:<52} added/updated/skipped = {actual} (expected {expected})")
    if "--keep" not in sys.argv:
        client.file_search_stores.delete(name=store.name, config={"force": True})
        print("demo store deleted")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
