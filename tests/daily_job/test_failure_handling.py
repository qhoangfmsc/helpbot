"""The job must never hang or fail silently: each failure ends with a specific log message and the right exit code."""

import logging
import threading

import httpx
import requests
from google.genai import errors

from helpbot.pipeline import sync_store
from tests.support import FakeStore, make_article, make_local, run_main

DAILY = errors.ClientError(429, {"error": {"message": "quota", "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})


class FailingStore(FakeStore):
    """Raises `error` for the given article ids (all when `only` is None)."""

    def __init__(self, error, only=None):
        super().__init__()
        self.error, self.only = error, only

    def upload(self, path, article_id, content_hash):
        self.calls.append(("upload", article_id))
        if self.only is None or article_id in self.only:
            raise self.error


def test_daily_quota_stops_the_run_after_the_first_failure(tmp_path):
    local = make_local(tmp_path, **{str(i): f"text {i}" for i in range(1, 9)})
    store = FailingStore(DAILY)
    summary = sync_store(local, store, workers=1)
    assert store.uploaded_ids == ["1"]  # the other seven were not even tried
    assert summary.failed == 8 and not summary.ok
    assert any("DAILY quota" in p for p in summary.problems) and len(summary.problems) == 1


def test_a_timeout_on_one_article_does_not_stop_the_others(tmp_path):
    local = make_local(tmp_path, **{"1": "a", "2": "b", "3": "c"})
    store = FailingStore(httpx.ReadTimeout("slow"), only={"2"})
    summary = sync_store(local, store, workers=1)
    assert sorted(store.uploaded_ids) == ["1", "2", "3"]
    assert (summary.failed, summary.problems) == (1, [])  # reported per file in the log; the next run retries it


def test_time_limit_skips_the_remaining_uploads_instead_of_running_on(tmp_path):
    local = make_local(tmp_path, **{str(i): f"text {i}" for i in range(1, 6)})
    store = FakeStore()
    summary = sync_store(local, store, workers=1, max_seconds=-1)  # already over the limit
    assert store.calls == [] and summary.failed == 5
    assert "time limit" in summary.problems[0]


def test_upload_failures_log_the_specific_reason(tmp_path, caplog):
    local = make_local(tmp_path, **{"1": "a"})
    with caplog.at_level(logging.ERROR, logger="helpbot.pipeline"):
        sync_store(local, FailingStore(httpx.ConnectError("down")), workers=1)
    assert "Cannot reach the server" in caplog.text and "article_id=1" in caplog.text
    assert "Traceback" not in caplog.text  # known problems are explained, not dumped


def test_exit_code_1_when_some_uploads_fail(monkeypatch, tmp_path):
    store = FailingStore(httpx.ReadTimeout("slow"), only={"2"})
    assert run_main(monkeypatch, tmp_path, store, [make_article(i) for i in (1, 2, 3)]) == 1


def test_exit_code_3_and_a_clear_message_when_the_store_cannot_be_opened(monkeypatch, tmp_path, caplog):
    import main

    def refuse(client, name):
        raise DAILY

    monkeypatch.setattr(main.FileSearchStore, "open", staticmethod(refuse), raising=True)
    with caplog.at_level(logging.ERROR, logger="helpbot"):
        code = _run_without_store_patch(monkeypatch, tmp_path)
    assert code == 3 and "DAILY quota" in caplog.text


def _run_without_store_patch(monkeypatch, tmp_path):
    import main

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ARTICLES_DIR", str(tmp_path / "out"))
    ids = tmp_path / "ids.txt"
    ids.write_text("1\n", encoding="utf-8")
    monkeypatch.setenv("ARTICLE_IDS_FILE", str(ids))
    monkeypatch.setattr(main, "fetch_articles", lambda base_url: iter([make_article(1)]))
    monkeypatch.setattr(main, "make_client", lambda api_key: object())
    return main.main()


def test_exit_code_3_when_the_help_center_times_out(monkeypatch, tmp_path, caplog):
    import main

    def timeout(base_url):
        raise requests.exceptions.ReadTimeout()

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main, "fetch_articles", timeout)
    with caplog.at_level(logging.ERROR, logger="helpbot"):
        assert main.main() == 3
    assert "Timed out waiting for the server" in caplog.text


def test_exit_code_3_when_the_network_is_down(monkeypatch, tmp_path, caplog):
    import main

    def down(base_url):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main, "fetch_articles", down)
    with caplog.at_level(logging.ERROR, logger="helpbot"):
        assert main.main() == 3
    assert "Cannot reach the server" in caplog.text


def test_exit_code_2_for_a_missing_key_and_nothing_is_called(monkeypatch, caplog):
    import main

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(main, "fetch_articles", lambda base_url: (_ for _ in ()).throw(AssertionError("must not be called")))
    assert main.main() == 2


def test_an_unexpected_bug_still_exits_non_zero_with_a_traceback(monkeypatch, tmp_path, caplog):
    import main

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main, "fetch_articles", lambda base_url: (_ for _ in ()).throw(KeyError("boom")))
    with caplog.at_level(logging.ERROR, logger="helpbot"):
        assert main.main() == 3
    assert "Unexpected KeyError" in caplog.text and "Traceback" in caplog.text
