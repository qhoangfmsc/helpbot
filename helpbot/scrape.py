"""Scrape articles and write one Markdown file per article."""

import logging
from pathlib import Path

from helpbot.markdown import render_article, slugify
from helpbot.zendesk import Article

log = logging.getLogger(__name__)


def write_articles(articles: list[Article], out_dir: Path) -> dict[str, Path]:
    """Write `<slug>.md` per article; returns article id -> file path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for article in articles:
        path = out_dir / f"{slugify(article)}.md"
        path.write_text(render_article(article), encoding="utf-8")
        written[article.id] = path
    log.info("wrote files=%s dir=%s", len(written), out_dir)
    return written
