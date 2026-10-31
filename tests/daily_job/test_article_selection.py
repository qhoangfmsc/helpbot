"""The job syncs a fixed list of articles (config/article_ids.txt), not the whole Help Center."""

import pytest

from helpbot.scrape import load_ids, select_ids
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
    assert run_main(monkeypatch, tmp_path, store, articles, ARTICLE_IDS_FILE=ids_file(tmp_path, "2", "5", "9")) == 0
    assert sorted(store.uploaded_ids) == ["2", "5", "9"]


def test_second_run_over_the_same_list_skips_everything(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i) for i in range(1, 11)]
    env = {"ARTICLE_IDS_FILE": ids_file(tmp_path, "2", "5", "9")}
    run_main(monkeypatch, tmp_path, store, articles, **env)
    store.calls.clear()
    assert run_main(monkeypatch, tmp_path, store, articles, **env) == 0
    assert store.calls == []


def test_documents_of_articles_removed_from_the_list_are_deleted(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i) for i in range(1, 11)]
    run_main(monkeypatch, tmp_path, store, articles, ARTICLE_IDS_FILE=ids_file(tmp_path, "1", "2", "3", "4"))
    run_main(monkeypatch, tmp_path, store, articles, ARTICLE_IDS_FILE=ids_file(tmp_path, "1", "2", "3"))
    assert sorted(d.article_id for d in store.docs) == ["1", "2", "3"]


def test_a_listed_id_that_is_gone_from_the_site_is_a_warning_not_a_failure(monkeypatch, tmp_path, caplog):
    store = FakeStore()
    articles = [make_article(1), make_article(2)]
    code = run_main(monkeypatch, tmp_path, store, articles, ARTICLE_IDS_FILE=ids_file(tmp_path, "1", "2", "404"))
    assert code == 0 and sorted(store.uploaded_ids) == ["1", "2"]
    assert "404" in caplog.text


def test_missing_ids_file_exits_with_code_2_and_uploads_nothing(monkeypatch, tmp_path):
    store = FakeStore()
    assert run_main(monkeypatch, tmp_path, store, [make_article(1)], ARTICLE_IDS_FILE=str(tmp_path / "nope.txt")) == 2
    assert store.calls == []


def test_a_list_that_matches_nothing_fails_instead_of_wiping_the_store(monkeypatch, tmp_path):
    store = FakeStore([RemoteDoc("docs/1", "1", "h"), RemoteDoc("docs/2", "2", "h")])
    with pytest.raises(ValueError, match="no articles"):
        run_main(monkeypatch, tmp_path, store, [make_article(1)], ARTICLE_IDS_FILE=ids_file(tmp_path, "999"))
    assert len(store.docs) == 2
