"""Read articles from a public Zendesk Help Center API."""

import logging
from dataclasses import dataclass
from typing import Iterator

import requests

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://support.optisigns.com"
DEFAULT_LOCALE = "en-us"
PER_PAGE = 100
TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    html_url: str
    updated_at: str
    body_html: str


def fetch_articles(
    base_url: str = DEFAULT_BASE_URL,
    locale: str = DEFAULT_LOCALE,
    session: requests.Session | None = None,
) -> Iterator[Article]:
    """Yield every published article, following Zendesk's `next_page` links."""
    session = session or requests.Session()
    url: str | None = f"{base_url}/api/v2/help_center/{locale}/articles.json"
    params: dict[str, int] | None = {"per_page": PER_PAGE}
    while url:
        resp = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        log.info("fetched page=%s/%s count=%s", data["page"], data["page_count"], data["count"])
        for raw in data["articles"]:
            if raw.get("draft") or not raw.get("body"):
                continue
            yield Article(
                id=str(raw["id"]),
                title=raw["title"].strip(),
                html_url=raw["html_url"],
                updated_at=raw["updated_at"],
                body_html=raw["body"],
            )
        url, params = data.get("next_page"), None  # next_page already carries the query string
