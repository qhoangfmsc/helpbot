import pytest

from helpbot.scrape import write_articles
from helpbot.zendesk import Article


def article(id, title="T"):
    return Article(id=id, title=title, html_url=f"https://h/{id}", updated_at="2026-01-01T00:00:00Z", body_html="<p>x</p>")


def test_writes_one_file_per_article(tmp_path):
    written = write_articles([article("1", "One"), article("2", "Two")], tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["1-one.md", "2-two.md"]
    assert written["1"].read_text().startswith("# One\n\nArticle URL: https://h/1\n")


def test_removes_files_of_articles_that_disappeared(tmp_path):
    write_articles([article("1", "One"), article("2", "Two")], tmp_path)
    write_articles([article("2", "Two")], tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["2-two.md"]


def test_empty_fetch_is_an_error_and_keeps_existing_files(tmp_path):
    write_articles([article("1", "One")], tmp_path)
    with pytest.raises(ValueError):
        write_articles([], tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["1-one.md"]


def test_rewriting_is_idempotent(tmp_path):
    write_articles([article("1", "One")], tmp_path)
    first = (tmp_path / "1-one.md").read_text()
    write_articles([article("1", "One")], tmp_path)
    assert (tmp_path / "1-one.md").read_text() == first


def test_never_deletes_files_that_are_not_generated_articles(tmp_path):
    (tmp_path / "README.md").write_text("keep me")
    (tmp_path / "notes.md").write_text("keep me too")
    write_articles([article("1", "One")], tmp_path)
    write_articles([article("2", "Two")], tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2-two.md", "README.md", "notes.md"]
