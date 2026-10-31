"""Read articles from a public Zendesk Help Center API."""

import logging
from dataclasses import dataclass
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://support.optisigns.com"
DEFAULT_LOCALE = "en-us"
PER_PAGE = 100
TIMEOUT_SECONDS = 30
RETRY_STATUSES = (429, 500, 502, 503, 504)
MAX_RETRY_AFTER_SECONDS = 60  # cap a server-sent Retry-After so a cron run cannot hang for hours


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    html_url: str
    updated_at: str
    body_html: str


def retrying_session() -> requests.Session:
    """Session that retries transient failures with exponential backoff (honours a capped Retry-After)."""
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=RETRY_STATUSES,
        respect_retry_after_header=True,
        retry_after_max=MAX_RETRY_AFTER_SECONDS,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def fetch_articles(
    base_url: str = DEFAULT_BASE_URL,
    locale: str = DEFAULT_LOCALE,
    session: requests.Session | None = None,
) -> Iterator[Article]:
    """Yield every published article, following Zendesk's `next_page` links."""
    session = session or retrying_session()
    url: str | None = f"{base_url}/api/v2/help_center/{locale}/articles.json"
    params: dict[str, int] | None = {"per_page": PER_PAGE}
    while url:
        resp = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        log.info("read Help Center page %s/%s (the site has %s articles in total)", data["page"], data["page_count"], data["count"])
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
