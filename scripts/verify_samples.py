"""Fact-check scraped Markdown against the live Help Center.

Usage: python scripts/verify_samples.py [dir] [base_url]   (network; exit 1 on any failed check)

For every `<id>-<slug>.md` in `dir` (default samples/articles) the live article is fetched again and:
  1. title and `Article URL:` match the live article,
  2. the file is byte-identical to what the converter produces from the live article now (unchanged since scraping),
  3. words, link targets, image sources, code blocks and headings of the live HTML are all present in the Markdown
     (and nothing was added) - compared with plain regexes, independent of the converter,
  4. the public article page answers 200, carries the same title, and its article body has the same words.
"""

import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helpbot.markdown import render_article  # noqa: E402
from helpbot.zendesk import DEFAULT_BASE_URL, Article, retrying_session  # noqa: E402

WORD = re.compile(r"\w+", re.U)
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]*)\)")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]*)\)")
FENCE = re.compile(r"^[ \t]*```", re.M)
HEADING = re.compile(r"^(?:>\s*)*#{1,6} ", re.M)  # headings inside callout blockquotes count
AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
PAUSE_SECONDS = 0.3


def words_of_html(html: str) -> Counter:
    """Visible words of the source. An <iframe> has no text but is shown as a link (its title or URL)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for frame in soup.find_all("iframe"):
        frame.replace_with(f" {frame.get('title') or frame.get('src') or ''} ")
    words = Counter(w.lower() for w in WORD.findall(soup.get_text(" ").replace("\xa0", " ")))
    for ol in soup.find_all("ol"):  # Markdown writes `1.`, `2.`... for every <ol> item; the HTML only implies them
        start = int(ol.get("start", 1)) if str(ol.get("start", 1)).isdigit() else 1
        words.update(str(start + i) for i in range(len(ol.find_all("li", recursive=False))))
    return words


def words_of_markdown(body: str) -> Counter:
    text = AUTOLINK.sub(r"\1", IMAGE.sub(" ", body))  # image alt text is not visible article text
    text = LINK.sub(lambda m: m.group(0)[1 : m.group(0).index("](")], text)  # keep the link text, drop the URL
    return Counter(w.lower() for w in WORD.findall(text))


def diff(label: str, expected: Counter, actual: Counter) -> list[str]:
    missing, extra = expected - actual, actual - expected
    problems = []
    if missing:
        problems.append(f"{label}: missing {dict(list(missing.items())[:6])}")
    if extra:
        problems.append(f"{label}: extra {dict(list(extra.items())[:6])}")
    return problems


def check(path: Path, live: dict, page: requests.Response | None) -> list[str]:
    text = path.read_text(encoding="utf-8")
    article = Article(str(live["id"]), live["title"].strip(), live["html_url"], live["updated_at"], live["body"])
    problems = []
    if not text.startswith(f"# {' '.join(article.title.split())}\n"):
        problems.append("title differs from the live article")
    if f"\nArticle URL: {article.html_url}\n" not in text:
        problems.append("Article URL differs from the live html_url")
    if text != render_article(article):
        problems.append("file differs from a fresh conversion of the live article (changed since scraping?)")

    body = text.split("\n", 4)[4] if text.count("\n") >= 4 else ""  # drop title, blank, Article URL, blank
    soup = BeautifulSoup(article.body_html, "html.parser")
    problems += diff("words", words_of_html(article.body_html), words_of_markdown(body))
    for href in {a["href"] for a in soup.find_all("a", href=True) if a.get_text(strip=True) or a.find("img")}:
        if href not in body:  # as [text](url), <url> autolink, or plain text inside a code block
            problems.append(f"link target lost: {href[:80]}")
    md_images = set(IMAGE.findall(body))
    for src in {i["src"] for i in soup.find_all("img", src=True)} - md_images:
        problems.append(f"image lost: {src[:80]}")
    if len(soup.find_all("pre")) != len(FENCE.findall(body)) // 2:
        problems.append(f"code blocks: source {len(soup.find_all('pre'))} vs markdown {len(FENCE.findall(body)) // 2}")
    source_headings = sum(1 for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]) if h.get_text(strip=True) or h.find(["img", "iframe"]))
    if source_headings != len(HEADING.findall(body)):
        problems.append(f"headings: source {source_headings} vs markdown {len(HEADING.findall(body))}")

    if page is None or page.status_code != 200:
        problems.append(f"public page not verifiable: HTTP {getattr(page, 'status_code', 'error')}")
    else:
        psoup = BeautifulSoup(page.text, "html.parser")
        page_title = psoup.title.get_text(strip=True) if psoup.title else ""
        if article.title not in page_title:
            problems.append(f"public page title {page_title!r} does not contain {article.title!r}")
        body_div = psoup.select_one(".article-body")
        if body_div is None:
            problems.append("public page has no .article-body")
        else:
            problems += diff("public page words", words_of_html(str(body_div)), words_of_markdown(body))
    return problems


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/articles")
    base = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_BASE_URL
    session = retrying_session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; helpbot-verify)"
    files = sorted(folder.glob("*.md"))
    failed = 0
    for path in files:
        article_id = path.name.split("-")[0]
        resp = session.get(f"{base}/api/v2/help_center/en-us/articles/{article_id}.json", timeout=30)
        if resp.status_code != 200:
            problems = [f"live article API answered HTTP {resp.status_code}"]
        else:
            live = resp.json()["article"]
            try:
                page = session.get(live["html_url"], timeout=30)
            except requests.RequestException:
                page = None
            problems = check(path, live, page)
        failed += bool(problems)
        print(("FAIL " if problems else "ok   ") + path.name + "".join(f"\n       - {p}" for p in problems))
        time.sleep(PAUSE_SECONDS)
    print(f"{len(files) - failed}/{len(files)} files verified against the live site")
    return 1 if failed or not files else 0


if __name__ == "__main__":
    sys.exit(main())
