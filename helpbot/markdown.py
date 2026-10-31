"""Turn a Help Center article into clean Markdown. Pure functions, no network."""

import re

from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify

from helpbot.zendesk import Article

_KEEP_ATTRS = {"a": {"href"}, "img": {"src", "alt"}, "iframe": {"src", "title"}, "ol": {"start"}}  # `start`: steps continue across lists
_IMAGE_PARENTS = ["td", "th", "a", "h1", "h2", "h3", "h4", "h5", "h6"]
_INLINE_EMPHASIS = ["strong", "b", "em", "i", "u"]
_SINGLE_CHILD_WRAPPERS = ["p", "figure", "strong", "b", "em", "i", "u"]
_BLANK_LINES = re.compile(r"\n{3,}")
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))  # zero-width chars
_HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]


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
    for text in soup.find_all(string=True):  # first, so `<h2>\u200b</h2>` counts as empty below
        if type(text) is NavigableString:
            text.replace_with(_normalize_chars(str(text)))
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for img in soup.find_all("img"):  # inline base64 image: ~100 KB of noise for search, and it breaks the store upload
        if (img.get("src") or "").startswith("data:"):
            img.replace_with(img.get("alt") or "")
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
    for img in soup.find_all("img"):  # markdownify only looks at the direct parent of an inline-context image
        if img.find_parent(_IMAGE_PARENTS):
            while img.parent.name in _SINGLE_CHILD_WRAPPERS and len(img.parent.contents) == 1:
                img.parent.unwrap()
    for tag in soup.find_all(True):
        allowed = _KEEP_ATTRS.get(tag.name, set())
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed}
    for span in soup.find_all("span"):  # styling only; unwrap (not drop) so spaces between inline tags survive
        span.unwrap()
    for tag in soup.find_all(_INLINE_EMPHASIS):  # `<strong> </strong>` is just a space, Markdown would drop it
        if not tag.get_text(strip=True) and not tag.find(["img", "a"]):
            tag.replace_with(" " if tag.get_text() else "")
    for link in soup.find_all("a"):  # a link with neither text nor image points at nothing visible
        if not link.get_text(strip=True) and not link.find("img"):
            link.decompose()
    for tag in soup.find_all(["p", "li", *_HEADINGS]):  # empty wrappers left by the editor
        if not tag.get_text(strip=True) and not tag.find(["img", "a"]):
            tag.decompose()
    return soup


def _normalize_chars(text: str) -> str:
    """Non-breaking spaces become plain spaces and zero-width characters are removed (also inside code:
    in practice they are copy-paste artefacts there, and they would break copying a command)."""
    return text.replace("\xa0", " ").translate(_INVISIBLE)


def html_to_markdown(html: str) -> str:
    text = markdownify(
        str(_clean(html)),
        heading_style="ATX",
        bullets="-",
        escape_underscores=False,
        keep_inline_images_in=_IMAGE_PARENTS,  # by default images in tables/links/headings are dropped
    )
    return _BLANK_LINES.sub("\n\n", _normalize_chars(text)).strip()


def render_article(article: Article) -> str:
    """Final file content. `Article URL:` is a literal line so the bot can cite it."""
    title = " ".join(_normalize_chars(article.title).split())
    body = html_to_markdown(article.body_html)
    return f"# {title}\n\nArticle URL: {article.html_url}\n\n{body}\n"
