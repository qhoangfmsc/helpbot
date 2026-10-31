"""Daily job entry point: scrape -> delta -> upload. Runs once and exits.

Exit codes: 0 ok | 1 some uploads failed (next run retries) | 2 configuration/input problem | 3 API or network problem.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from helpbot.pipeline import run_job
from helpbot.problems import EXIT_API, EXIT_CONFIG, EXIT_SOME_FAILED, classify, explain
from helpbot.scrape import load_ids, select_ids
from helpbot.store import DEFAULT_STORE_NAME, FileSearchStore, make_client
from helpbot.zendesk import DEFAULT_BASE_URL, fetch_articles

log = logging.getLogger("helpbot")

DEFAULT_IDS_FILE = "config/article_ids.txt"  # the 40 articles the job keeps in sync
DEFAULT_JOB_MAX_MINUTES = 30  # a stuck run must end well before the workflow's own 45-minute cut-off


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "google_genai", "urllib3"):  # one INFO line per HTTP call would bury the summary
        logging.getLogger(noisy).setLevel(logging.WARNING)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY is not set (see .env.sample)")
        return EXIT_CONFIG
    try:
        summary = _run(api_key)
    except Exception as error:  # every known failure has its own message; only unknown ones get a traceback
        kind = classify(error)
        if kind == "unknown":
            log.exception("job aborted: %s", explain(error))
        else:
            log.error("job aborted: %s", explain(error))
        return EXIT_CONFIG if kind == "input" else EXIT_API
    if summary is None:
        return EXIT_CONFIG
    log.info("done %s", summary.line())
    return 0 if summary.ok else EXIT_SOME_FAILED


def _run(api_key: str):
    limit = int(os.environ["ARTICLE_LIMIT"]) if os.environ.get("ARTICLE_LIMIT") else None
    articles = list(fetch_articles(os.environ.get("HELP_CENTER_URL", DEFAULT_BASE_URL)))
    ids_file = os.environ.get("ARTICLE_IDS_FILE", DEFAULT_IDS_FILE)
    try:
        articles, missing = select_ids(articles, load_ids(Path(ids_file)))
    except (OSError, ValueError) as error:
        log.error("cannot use ARTICLE_IDS_FILE=%s: %s", ids_file, error)
        return None
    if missing:
        log.warning("%s listed article ids are not on the site any more: %s", len(missing), ", ".join(missing))
    store = FileSearchStore.open(make_client(api_key), os.environ.get("GEMINI_FILE_SEARCH_STORE", DEFAULT_STORE_NAME))
    minutes = float(os.environ.get("JOB_MAX_MINUTES", DEFAULT_JOB_MAX_MINUTES))
    return run_job(
        articles,
        Path(os.environ.get("ARTICLES_DIR", "articles")),
        store,
        workers=int(os.environ.get("UPLOAD_WORKERS", "4")),
        limit=limit,
        max_seconds=minutes * 60,
    )


if __name__ == "__main__":
    sys.exit(main())
