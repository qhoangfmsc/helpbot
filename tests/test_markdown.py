from helpbot.markdown import html_to_markdown, render_article, slugify
from helpbot.zendesk import Article


def make_article(**overrides) -> Article:
    fields = dict(
        id="42",
        title="How to Use YouTube",
        html_url="https://help.example.com/hc/en-us/articles/42-How-to-Use-YouTube",
        updated_at="2026-01-01T00:00:00Z",
        body_html="<p>Hello</p>",
    )
    return Article(**{**fields, **overrides})


def test_headings_links_and_lists_are_preserved():
    md = html_to_markdown(
        '<h2 id="x">Setup</h2><ul><li><a href="/hc/en-us/articles/1">Relative</a></li>'
        '<li><a href="#anchor">Jump</a></li></ul>'
    )
    assert "## Setup" in md
    assert "- [Relative](/hc/en-us/articles/1)" in md
    assert "- [Jump](#anchor)" in md


def test_code_blocks_and_inline_code_are_preserved():
    md = html_to_markdown("<p>Run <code>docker run</code>:</p><pre>echo hi\nexit 0</pre>")
    assert "`docker run`" in md
    assert "```\necho hi\nexit 0\n```" in md


def test_editor_noise_is_removed():
    md = html_to_markdown(
        '<p><a name="Jump"></a></p><p style="color:red" data-x="1">Text</p><script>alert(1)</script><p>&nbsp;</p>'
    )
    assert md == "Text"


def test_single_column_table_becomes_blockquote():
    md = html_to_markdown("<table><tbody><tr><td><strong>TIP</strong></td></tr><tr><td>Be nice</td></tr></tbody></table>")
    assert "|" not in md
    assert md.startswith("> **TIP**")
    assert "> Be nice" in md


def test_table_without_header_gets_a_header_row():
    md = html_to_markdown("<table><tbody><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></tbody></table>")
    assert md.splitlines()[0] == "| A | B |"
    assert md.splitlines()[1] == "| --- | --- |"


def test_images_inside_table_cells_are_kept():
    md = html_to_markdown('<table><tbody><tr><td>A</td><td>B</td></tr><tr><td><figure><p><img src="https://x/1"></p></figure></td><td>t</td></tr></tbody></table>')
    assert "![](https://x/1)" in md


def test_iframe_becomes_a_link():
    md = html_to_markdown('<iframe src="https://www.youtube.com/embed/abc" title="Demo"></iframe>')
    assert md == "[Demo](https://www.youtube.com/embed/abc)"


def test_render_article_has_title_and_article_url_line():
    out = render_article(make_article())
    assert out.startswith("# How to Use YouTube\n\nArticle URL: https://help.example.com/hc/en-us/articles/42-How-to-Use-YouTube\n\n")
    assert out.endswith("Hello\n")


def test_slug_is_stable_unique_and_filesystem_safe():
    assert slugify(make_article()) == "42-how-to-use-youtube"
    assert slugify(make_article(title="¿Qué? / & more!")) == "42-qu-more"
    assert slugify(make_article(title="???")) == "42"
