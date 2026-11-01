"""The committed articles/ folder is what a reviewer reads first: every file must be spec-compliant."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTICLES = sorted((ROOT / "articles").glob("*.md"))

_spec = importlib.util.spec_from_file_location("check_markdown", ROOT / "scripts" / "check_markdown.py")
check_markdown = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_markdown)


def all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ARTICLES)


def test_at_least_thirty_articles_are_committed():
    assert len(ARTICLES) >= 30


def test_every_sample_is_clean_markdown_with_a_single_article_url():
    problems = {p.name: check_markdown.check(p) for p in ARTICLES if check_markdown.check(p)}
    assert problems == {}


def test_file_names_follow_the_id_slug_scheme():
    assert all(re.fullmatch(r"\d+-[a-z0-9-]+\.md", p.name) for p in ARTICLES)


def test_the_article_that_answers_the_sample_question_is_included():
    assert any("youtube" in p.name for p in ARTICLES)


def test_headings_code_blocks_links_and_tables_are_preserved_somewhere():
    text = all_text()
    assert re.search(r"^## ", text, re.M)  # headings
    assert re.search(r"^[ \t]*```", text, re.M)  # code blocks
    assert re.search(r"\]\(#[^)]+\)", text) or re.search(r"\]\(/[^)]+\)", text)  # relative / in-page links
    assert re.search(r"^\| --- \|", text, re.M)  # tables
    assert re.search(r"!\[[^\]]*\]\(https://", text)  # images


def test_no_navigation_or_ad_boilerplate_survived():
    text = all_text().lower()
    for noise in ("skip to main content", "submit a request", "was this article helpful", "powered by zendesk"):  # Help Center chrome
        assert noise not in text


def test_every_listed_article_is_committed_including_youtube():
    from_file = (ROOT / "config" / "article_ids.txt").read_text(encoding="utf-8").splitlines()
    ids = [line for line in from_file if line and not line.startswith("#")]
    assert set(ids) <= {p.name.split("-")[0] for p in ARTICLES}  # the folder may also hold the newest articles
    assert "360051014713" in ids  # "How to Use YouTube with ..." answers the sample question
