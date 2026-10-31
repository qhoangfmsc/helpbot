"""Daily job entry point: scrape -> delta -> upload. Runs once and exits.

Usage: python main.py [--allow-mass-delete] [--limit N]
Settings: config/settings.toml. The only environment variable is GEMINI_API_KEY (.env).
Exit codes: 0 ok | 1 some uploads failed (next run retries) | 2 configuration/input problem | 3 API or network problem.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from helpbot.pipeline import run_job
from helpbot.problems import EXIT_API, EXIT_CONFIG, EXIT_SOME_FAILED, classify, explain
from helpbot.scrape import load_ids, select_ids
from helpbot.settings import ROOT, Settings, load_settings
from helpbot.store import FileSearchStore, make_client
from helpbot.zendesk import fetch_articles

log = logging.getLogger("helpbot")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sync", description="Sync the Help Center articles into the Gemini store (only changes are uploaded).")
    parser.add_argument("--allow-mass-delete", action="store_true",
                        help="one-off cleanup: allow deleting more than half of the store (after deliberately shrinking the article list)")
    parser.add_argument("--limit", type=int, metavar="N", help="partial run: only the N most recently updated articles; never deletes")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "google_genai", "urllib3"):  # one INFO line per HTTP call would bury the summary
        logging.getLogger(noisy).setLevel(logging.WARNING)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY is not set (copy .env.sample to .env and put your key in it)")
        return EXIT_CONFIG
    try:
        summary = _run(api_key, settings or load_settings(), args)
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


def _run(api_key: str, settings: Settings, args: argparse.Namespace):
    all_articles = list(fetch_articles(settings.help_center_url))
    ids_file = settings.path(settings.article_ids_file)
    try:
        articles, missing = select_ids(all_articles, load_ids(ids_file))
    except (OSError, ValueError) as error:
        log.error("cannot use article_ids_file=%s: %s", settings.article_ids_file, error)
        return None
    log.info("syncing %s of the %s articles on the site: only those listed in %s", len(articles), len(all_articles), settings.article_ids_file)
    if missing:
        log.warning("%s listed article ids are not on the site any more: %s", len(missing), ", ".join(missing))
    store = FileSearchStore.open(make_client(api_key, settings.request_timeout_seconds), settings.store_name)
    return run_job(
        articles,
        settings.path(settings.articles_dir),
        store,
        workers=settings.upload_workers,
        limit=args.limit,
        max_seconds=settings.job_max_minutes * 60,
        allow_mass_delete=args.allow_mass_delete,
    )


if __name__ == "__main__":
    sys.exit(main())
