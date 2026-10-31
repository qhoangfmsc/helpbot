"""The task requires logging how many files and chunks were embedded."""

import logging

from tests.support import FakeStore, make_article, run_main


def test_run_logs_files_and_chunks_embedded(monkeypatch, tmp_path, caplog):
    long_body = "<p>" + "word " * 1500 + "</p>"  # ~1.9k tokens -> several chunks
    articles = [make_article(1, body=long_body), make_article(2)]
    with caplog.at_level(logging.INFO, logger="helpbot"):
        run_main(monkeypatch, tmp_path, FakeStore(), articles)
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("done "))
    fields = dict(part.split("=") for part in line.removeprefix("done ").split())
    assert fields["files"] == "2"
    assert int(fields["chunks_estimated"]) > 2  # the long article alone needs several chunks
    assert fields["store_documents"] == "2"


def test_second_run_embeds_nothing(monkeypatch, tmp_path, caplog):
    store, articles = FakeStore(), [make_article(1), make_article(2)]
    run_main(monkeypatch, tmp_path, store, articles)
    with caplog.at_level(logging.INFO, logger="helpbot"):
        run_main(monkeypatch, tmp_path, store, articles)
    assert any("files=0 chunks_estimated=0" in r.getMessage() for r in caplog.records)
