"""The job syncs the listed articles (config/article_ids.txt) plus the newest ones, not the whole Help Center."""

import pytest

from helpbot.scrape import choose, load_ids, select_ids
from helpbot.sync import RemoteDoc
from tests.support import FakeStore, make_article, run_main


def test_load_ids_ignores_comments_and_blank_lines(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("# header\n101\n\n 102  # inline note\n", encoding="utf-8")
    assert load_ids(path) == ["101", "102"]


def test_load_ids_rejects_lines_that_are_not_ids(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("101\nnot-an-id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not-an-id"):
        load_ids(path)


def test_select_ids_keeps_listed_articles_and_reports_the_missing_ones():
    articles = [make_article(i) for i in (1, 2, 3, 4)]
    selected, missing = select_ids(articles, ["2", "4", "99", "7"])
    assert [a.id for a in selected] == ["2", "4"]
    assert missing == ["7", "99"]


def ids_file(tmp_path, *ids):
    path = tmp_path / "ids.txt"
    path.write_text("\n".join(ids) + "\n", encoding="utf-8")
    return str(path)


def test_job_uploads_only_the_listed_articles(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i) for i in range(1, 11)]
    assert run_main(monkeypatch, tmp_path, store, articles, ids_file=ids_file(tmp_path, "2", "5", "9")) == 0
    assert sorted(store.uploaded_ids) == ["2", "5", "9"]


def test_second_run_over_the_same_list_skips_everything(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i) for i in range(1, 11)]
    env = {"ids_file": ids_file(tmp_path, "2", "5", "9")}
    run_main(monkeypatch, tmp_path, store, articles, **env)
    store.calls.clear()
    assert run_main(monkeypatch, tmp_path, store, articles, **env) == 0
    assert store.calls == []


def test_an_article_dropped_from_the_list_keeps_its_document_while_it_is_still_on_the_site(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i) for i in range(1, 11)]
    run_main(monkeypatch, tmp_path, store, articles, ids_file=ids_file(tmp_path, "1", "2", "3", "4"))
    run_main(monkeypatch, tmp_path, store, articles, ids_file=ids_file(tmp_path, "1", "2", "3"))
    assert sorted(d.article_id for d in store.docs) == ["1", "2", "3", "4"]


def test_the_document_of_an_article_deleted_from_the_site_is_removed(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i) for i in range(1, 11)]
    run_main(monkeypatch, tmp_path, store, articles, ids_file=ids_file(tmp_path, "1", "2", "3", "4"))
    run_main(monkeypatch, tmp_path, store, [a for a in articles if a.id != "4"], ids_file=ids_file(tmp_path, "1", "2", "3", "4"))
    assert sorted(d.article_id for d in store.docs) == ["1", "2", "3"]


def test_a_listed_id_that_is_gone_from_the_site_is_a_warning_not_a_failure(monkeypatch, tmp_path, caplog):
    store = FakeStore()
    articles = [make_article(1), make_article(2)]
    code = run_main(monkeypatch, tmp_path, store, articles, ids_file=ids_file(tmp_path, "1", "2", "404"))
    assert code == 0 and sorted(store.uploaded_ids) == ["1", "2"]
    assert "404" in caplog.text


def test_missing_ids_file_exits_with_code_2_and_uploads_nothing(monkeypatch, tmp_path):
    store = FakeStore()
    assert run_main(monkeypatch, tmp_path, store, [make_article(1)], ids_file=str(tmp_path / "nope.txt")) == 2
    assert store.calls == []


def test_a_list_that_matches_nothing_fails_instead_of_wiping_the_store(monkeypatch, tmp_path, caplog):
    store = FakeStore([RemoteDoc("docs/1", "1", "h"), RemoteDoc("docs/2", "2", "h")])
    code = run_main(monkeypatch, tmp_path, store, [make_article(1)], ids_file=ids_file(tmp_path, "999"))
    assert code == 2 and "no articles to write" in caplog.text
    assert len(store.docs) == 2


def dated(n):
    """Articles 1..n where a higher id means more recently updated."""
    return [make_article(i, updated_at=f"2026-01-{i:02d}T00:00:00Z") for i in range(1, n + 1)]


def test_choose_returns_the_listed_articles_plus_the_newest_ones_each_once():
    selected, missing = choose(dated(10), ["9", "2", "404"], newest=3)  # newest 3 = 10, 9, 8; 9 is also listed
    assert [a.id for a in selected] == ["2", "8", "9", "10"] and missing == ["404"]


def test_choose_with_zero_newest_is_just_the_listed_articles():
    selected, _ = choose(dated(10), ["2"], newest=0)
    assert [a.id for a in selected] == ["2"]


def test_job_syncs_the_listed_article_plus_the_newest_and_nothing_else(monkeypatch, tmp_path):
    store = FakeStore()
    assert run_main(monkeypatch, tmp_path, store, dated(10), ids_file=ids_file(tmp_path, "1"), newest_articles=2) == 0
    assert sorted(store.uploaded_ids) == ["1", "10", "9"]


def test_a_new_article_is_added_and_one_pushed_out_of_the_newest_window_is_kept(monkeypatch, tmp_path):
    store = FakeStore()
    env = {"ids_file": ids_file(tmp_path, "1"), "newest_articles": 2}
    run_main(monkeypatch, tmp_path, store, dated(10), **env)
    store.calls.clear()
    assert run_main(monkeypatch, tmp_path, store, dated(11), **env) == 0  # a new article, 11, becomes the newest
    assert store.uploaded_ids == ["11"] and not any(c[0] == "delete" for c in store.calls)
    assert sorted(d.article_id for d in store.docs) == ["1", "10", "11", "9"]  # 9 is no longer among the newest 2 but stays
