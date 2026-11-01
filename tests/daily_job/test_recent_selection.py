"""latest(): the newest-articles window picks the most recently updated ones, reproducibly."""

from helpbot.scrape import latest
from tests.support import make_article


def test_picks_the_most_recently_updated_articles_first():
    articles = [
        make_article(1, updated_at="2026-01-01T00:00:00Z"),
        make_article(2, updated_at="2026-03-01T00:00:00Z"),
        make_article(3, updated_at="2026-02-01T00:00:00Z"),
    ]
    assert [a.id for a in latest(articles, 2)] == ["2", "3"]


def test_ties_are_broken_by_higher_id_so_the_selection_is_reproducible():
    articles = [make_article(i, updated_at="2026-01-01T00:00:00Z") for i in (5, 20, 3)]
    assert [a.id for a in latest(articles, 3)] == ["20", "5", "3"]


def test_limit_larger_than_the_list_returns_everything():
    assert len(latest([make_article(1), make_article(2)], 40)) == 2
