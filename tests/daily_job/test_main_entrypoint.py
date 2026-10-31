import logging

from tests.support import FakeStore, make_article, run_main


def test_missing_api_key_exits_with_code_2(monkeypatch):
    import main

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert main.main() == 2


def test_successful_run_exits_0_and_logs_the_summary(monkeypatch, tmp_path, caplog):
    store = FakeStore()
    with caplog.at_level(logging.INFO, logger="helpbot"):
        code = run_main(monkeypatch, tmp_path, store, [make_article(i) for i in range(1, 4)])
    assert code == 0
    assert sorted(store.uploaded_ids) == ["1", "2", "3"]
    assert any("done added=3 updated=0 skipped=0" in r.getMessage() for r in caplog.records)


def test_failed_upload_makes_the_job_exit_non_zero(monkeypatch, tmp_path):
    store = FakeStore(fail_uploads={"2"})
    assert run_main(monkeypatch, tmp_path, store, [make_article(i) for i in range(1, 4)]) == 1
    assert sorted(d.article_id for d in store.docs) == ["1", "3"]  # the others still made it


def test_article_limit_env_selects_the_newest_articles(monkeypatch, tmp_path):
    store = FakeStore()
    articles = [make_article(i, updated_at=f"2026-01-{i:02d}T00:00:00Z") for i in range(1, 11)]
    assert run_main(monkeypatch, tmp_path, store, articles, ARTICLE_LIMIT="3") == 0
    assert sorted(store.uploaded_ids) == ["10", "8", "9"]
