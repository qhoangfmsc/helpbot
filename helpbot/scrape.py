"""Scrape articles and write one Markdown file per article."""

import logging
import re
from pathlib import Path

from helpbot.markdown import render_article, slugify
from helpbot.zendesk import Article

log = logging.getLogger(__name__)

_GENERATED_NAME = re.compile(r"\d+(-[a-z0-9-]*)?\.md")  # <article id>[-<slug>].md, see slugify()


def load_ids(path: Path) -> list[str]:
    """Article ids, one per line; blank lines and `#` comments are ignored."""
    ids = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            if not line.isdigit():
                raise ValueError(f"{path}: {line!r} is not an article id")
            ids.append(line)
    return ids


def select_ids(articles: list[Article], ids: list[str]) -> tuple[list[Article], list[str]]:
    """The articles whose id is listed (keeps the site's order) and the listed ids that were not found."""
    wanted = set(ids)
    selected = [a for a in articles if a.id in wanted]
    return selected, sorted(wanted - {a.id for a in selected}, key=int)


def latest(articles: list[Article], limit: int) -> list[Article]:
    """The `limit` most recently updated articles (ties: higher id first)."""
    return sorted(articles, key=lambda a: (a.updated_at, int(a.id)), reverse=True)[:limit]


def write_articles(articles: list[Article], out_dir: Path) -> dict[str, Path]:
    """Mirror `articles` into `out_dir` as `<slug>.md`; returns article id -> file path.

    Raises on an empty list (an outage must fail the job, not look like "everything was deleted") and
    removes generated `<id>-<slug>.md` files of articles that no longer exist (other files are never touched).
    """
    if not articles:
        raise ValueError("no articles to write; refusing to treat an empty fetch as success")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for article in articles:
        path = out_dir / f"{slugify(article)}.md"
        path.write_text(render_article(article), encoding="utf-8")
        written[article.id] = path
    current = set(written.values())
    stale = [p for p in out_dir.glob("*.md") if p not in current and _GENERATED_NAME.fullmatch(p.name)]
    for path in stale:
        path.unlink()
    log.info("wrote files=%s removed=%s dir=%s", len(written), len(stale), out_dir)
    return written
