"""Daily job entry point. Runs once and exits (0 on success). Stages are added milestone by milestone."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from helpbot.scrape import write_articles
from helpbot.zendesk import DEFAULT_BASE_URL, fetch_articles

log = logging.getLogger("helpbot")


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out_dir = Path(os.environ.get("ARTICLES_DIR", "data/articles"))
    articles = list(fetch_articles(os.environ.get("HELP_CENTER_URL", DEFAULT_BASE_URL)))
    write_articles(articles, out_dir)
    log.info("done articles=%s", len(articles))
    return 0


if __name__ == "__main__":
    sys.exit(main())
