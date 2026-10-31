"""Turn a Help Center article into clean Markdown. Pure functions, no network."""

import re

from bs4 import BeautifulSoup
from markdownify import markdownify

from helpbot.zendesk import Article

_KEEP_ATTRS = {"a": {"href"}, "img": {"src", "alt"}, "iframe": {"src", "title"}}
_IMAGE_PARENTS = ["td", "th", "a", "h1", "h2", "h3", "h4", "h5", "h6"]
_BLANK_LINES =re.compile(r"\n{3,}")


def slugify(article: Article) -> str:
    """`<id>-<title-slug>`: the id keeps filenames unique and stable if the title changes."""
    words = re.sub(r"[^a-z0-9]+", "-", article.title.lower()).strip("-")
    return f"{article.id}-{words[:80].strip('-')}" if words else article.id


def _normalize_table(soup: BeautifulSoup, table) -> None:
    """Zendesk tables have no <th>: Markdown would get an empty header row.

    One-column tables are callout boxes (TIP/NOTE) -> blockquote; otherwise the first row becomes the header.
    """
    rows = []
    for tr in table.find_all("tr"):
        if not tr.find(["td", "th"]):
            continue
        if not tr.get_text(strip=True) and not tr.find("img"):
            tr.decompose()  # blank spacer row
            continue
        rows.append(tr)
    if not rows:
        table.decompose()
    elif all(len(tr.find_all(["td", "th"])) == 1 for tr in rows):
        quote = soup.new_tag("blockquote")
        for tr in rows:
            cell = tr.find(["td", "th"])
            wrapper = soup.new_tag("div")
            wrapper.extend(list(cell.contents))
            quote.append(wrapper)
        table.replace_with(quote)
    elif not rows[0].find("th"):
        for cell in rows[0].find_all("td"):
            cell.name = "th"


def _clean(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for anchor in soup.find_all("a", attrs={"name": True}):
        if not anchor.get_text(strip=True):  # empty in-page jump targets
            anchor.decompose()
    for frame in soup.find_all("iframe"):  # embedded videos -> a plain link
        src = frame.get("src")
        if src:
            link = soup.new_tag("a", href=src)
            link.string = frame.get("title") or src
            paragraph = soup.new_tag("p")
            paragraph.append(link)
            frame.replace_with(paragraph)
        else:
            frame.decompose()
    for table in soup.find_all("table"):
        _normalize_table(soup, table)
    for img in soup.select("td img, th img"):  # markdownify only looks at the direct parent
        while img.parent.name in ("p", "figure") and len(img.parent.contents) == 1:
            img.parent.unwrap()
    for tag in soup.find_all(True):
        allowed = _KEEP_ATTRS.get(tag.name, set())
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed}
    for tag in soup.find_all(["p", "span", "li"]):  # empty wrappers left by the editor
        if not tag.get_text(strip=True) and not tag.find(["img", "a"]):
            tag.decompose()
    return soup


def html_to_markdown(html: str) -> str:
    text = markdownify(
        str(_clean(html)),
        heading_style="ATX",
        bullets="-",
        escape_underscores=False,
        keep_inline_images_in=_IMAGE_PARENTS,  # by default images in tables/links/headings are dropped
    )
    return _BLANK_LINES.sub("\n\n", text).strip()


def render_article(article: Article) -> str:
    """Final file content. `Article URL:` is a literal line so the bot can cite it."""
    body = html_to_markdown(article.body_html)
    return f"# {article.title}\n\nArticle URL: {article.html_url}\n\n{body}\n"
