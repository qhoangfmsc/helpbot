"""Daily job entry point: scrape -> delta -> upload. Runs once and exits (0 on success, non-zero on failure)."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from helpbot.pipeline import run_job
from helpbot.store import DEFAULT_STORE_NAME, FileSearchStore
from helpbot.zendesk import DEFAULT_BASE_URL, fetch_articles

log = logging.getLogger("helpbot")


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "google_genai", "urllib3"):  # one INFO line per HTTP call would bury the summary
        logging.getLogger(noisy).setLevel(logging.WARNING)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY is not set (see .env.sample)")
        return 2
    limit = int(os.environ["ARTICLE_LIMIT"]) if os.environ.get("ARTICLE_LIMIT") else None

    articles = list(fetch_articles(os.environ.get("HELP_CENTER_URL", DEFAULT_BASE_URL)))
    store = FileSearchStore.open(genai.Client(api_key=api_key), os.environ.get("GEMINI_FILE_SEARCH_STORE", DEFAULT_STORE_NAME))
    summary = run_job(
        articles,
        Path(os.environ.get("ARTICLES_DIR", "data/articles")),
        store,
        workers=int(os.environ.get("UPLOAD_WORKERS", "4")),
        limit=limit,
    )
    log.info("done %s", summary.line())
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
