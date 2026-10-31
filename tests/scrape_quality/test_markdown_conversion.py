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


def test_whitespace_only_span_between_inline_tags_keeps_the_space():
    assert html_to_markdown("<p><strong>Hello</strong><span> </span><strong>World</strong></p>") == "**Hello** **World**"
    assert html_to_markdown("<p>Click <a href='/x'>here</a><span> </span>now</p>") == "Click [here](/x) now"


def test_nbsp_only_paragraph_is_dropped():
    assert html_to_markdown("<p>&nbsp;</p><p>Text</p>") == "Text"


def test_span_styling_is_unwrapped_but_text_kept():
    assert html_to_markdown('<p><span style="color:red">Red</span> text</p>') == "Red text"


def test_whitespace_only_emphasis_tag_becomes_a_space():
    assert html_to_markdown('<p><a href="https://x.io"><strong>Postman</strong></a><strong>\xa0</strong>or other</p>') == "[**Postman**](https://x.io) or other"
    assert html_to_markdown("<p>a<strong></strong>b</p>") == "ab"


def test_nbsp_and_zero_width_characters_are_normalised():
    assert html_to_markdown("<p>a&nbsp;b\u200bc</p>") == "a bc"


def test_empty_headings_are_dropped_but_heading_with_image_is_kept():
    assert html_to_markdown("<h2> </h2><h3>&nbsp;</h3><p>Text</p>") == "Text"
    assert html_to_markdown('<h2><img src="https://x/1"></h2>') == "## ![](https://x/1)"


def test_title_whitespace_is_collapsed():
    assert render_article(make_article(title="How  to\xa0Use\n YouTube")).startswith("# How to Use YouTube\n")


def test_link_without_text_or_image_is_dropped_with_its_empty_heading():
    assert html_to_markdown('<h4><a href="https://x.io"> </a></h4><p>Text</p>') == "Text"


def test_image_wrapped_in_emphasis_inside_a_heading_is_kept():
    assert html_to_markdown('<h2><strong><img src="https://x/1"></strong></h2>') == "## ![](https://x/1)"


def test_zero_width_only_wrappers_count_as_empty():
    assert html_to_markdown("<h2>\u200b</h2><p>\u200b</p><p>Text</p>") == "Text"


def test_ordered_list_keeps_its_start_number():
    md = html_to_markdown('<ol><li>One</li></ol><p>x</p><ol start="2"><li>Two</li></ol><ol start="3"><li>Three</li><li>Four</li></ol>')
    assert "1. One" in md and "2. Two" in md and "3. Three" in md and "4. Four" in md


def test_inline_base64_images_are_dropped_but_their_alt_text_is_kept():
    big = "data:image/png;base64," + "A" * 5000
    assert html_to_markdown(f'<p>Before</p><p><img src="{big}"></p><p>After</p>') == "Before\n\nAfter"
    assert html_to_markdown(f'<p><img src="{big}" alt="QR code"></p>') == "QR code"
    assert html_to_markdown('<p><img src="https://x/1.png"></p>') == "![](https://x/1.png)"  # normal images stay
