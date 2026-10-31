"""scripts/check_store.py: the report that tells a reviewer whether the store matches articles/."""

import importlib.util
from pathlib import Path

from helpbot.sync import RemoteDoc, content_hash
from tests.support import make_local

_spec = importlib.util.spec_from_file_location("check_store", Path(__file__).resolve().parents[2] / "scripts" / "check_store.py")
check_store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_store)


def remote(article_id, text):
    return RemoteDoc(f"docs/{article_id}", article_id, content_hash(text))


def test_store_that_matches_the_files_is_in_sync(tmp_path):
    local = make_local(tmp_path, **{"1": "one", "2": "two"})
    report = check_store.build_report(local, [remote("1", "one"), remote("2", "two")])
    assert report == {"in_sync": ["1", "2"], "missing": [], "outdated": [], "extra": [], "duplicates": []}


def test_reports_missing_outdated_and_extra_documents(tmp_path):
    local = make_local(tmp_path, **{"1": "one", "2": "two NEW", "3": "three"})
    report = check_store.build_report(local, [remote("1", "one"), remote("2", "two OLD"), remote("9", "gone")])
    assert report["in_sync"] == ["1"] and report["missing"] == ["3"]
    assert report["outdated"] == ["2"] and report["extra"] == ["9"]


def article_file(folder, article_id, title, text="body"):
    path = folder / f"{article_id}-{title.lower().replace(' ', '-')}.md"
    path.write_text(f"# {title}\n\nArticle URL: https://help.example.com/hc/articles/{article_id}\n\n{text}\n", encoding="utf-8")
    return path


def test_each_article_is_listed_with_id_status_title_and_link(tmp_path):
    files = {"1": article_file(tmp_path, "1", "Add a YouTube video"), "3": article_file(tmp_path, "3", "Pair a screen", "new text")}
    local = check_store.load_local(files)
    stored = [RemoteDoc("fileSearchStores/s/documents/doc-1", "1", local["1"].hash), RemoteDoc("fileSearchStores/s/documents/doc-9", "9", "x")]
    text = check_store.format_articles(local, stored, check_store.build_report(local, stored))
    assert "1. 1" in text and "in sync" in text and "Add a YouTube video" in text and "https://help.example.com/hc/articles/1" in text
    assert "MISSING in store" in text and "Pair a screen" in text and "https://help.example.com/hc/articles/3" in text
    assert "EXTRA in store" in text and "doc-9" in text  # a document without a file is named so it can be found


def test_an_outdated_article_shows_both_hashes_for_debugging(tmp_path):
    files = {"1": article_file(tmp_path, "1", "Add a YouTube video")}
    local = check_store.load_local(files)
    stored = [RemoteDoc("docs/1", "1", "deadbeefdeadbeef")]
    text = check_store.format_articles(local, stored, check_store.build_report(local, stored))
    assert "OUTDATED in store" in text and f"hash {local['1'].hash[:8]} (store has deadbeef)" in text


def test_article_info_survives_a_file_without_title_or_link(tmp_path):
    path = tmp_path / "1-x.md"
    path.write_text("just text", encoding="utf-8")
    assert check_store.article_info(path) == ("(no title)", "(no Article URL line)")


def test_statistics_count_files_size_and_chunks(tmp_path):
    files = {"1": article_file(tmp_path, "1", "One"), "2": article_file(tmp_path, "2", "Two", "word " * 3000)}
    stats = check_store.format_local_stats(check_store.load_local(files))
    assert "2 files in articles/" in stats and "chunks estimated" in stats and "400 tokens per chunk" in stats
    counts = check_store.format_counts({"in_sync": ["1"], "missing": ["2"], "outdated": [], "extra": ["9"], "duplicates": []})
    assert "in sync 1" in counts and "missing in store 1" in counts and "extra in store 1" in counts


def test_check_store_main_points_to_the_override_when_most_of_the_store_is_extra(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace

    article_file(tmp_path, "1", "One", "one")  # check_store reads the id from the file name
    extras = [remote(str(i), "x") for i in range(2, 8)]

    class FakeStore:
        name = "fileSearchStores/s"

        def list_documents(self):
            return [RemoteDoc("docs/1", "1", content_hash(next(tmp_path.glob("1-*.md")).read_text(encoding="utf-8")))] + extras

    info = SimpleNamespace(display_name="helpbot-docs", active_documents_count=7, size_bytes=1024)
    client = SimpleNamespace(file_search_stores=SimpleNamespace(get=lambda name: info))
    from helpbot.settings import Settings

    monkeypatch.setattr(check_store, "load_dotenv", lambda path: None)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(check_store, "load_settings", lambda: Settings(articles_dir=str(tmp_path)))
    monkeypatch.setattr(check_store, "make_client", lambda key, timeout=None: client)
    monkeypatch.setattr(check_store.FileSearchStore, "open", staticmethod(lambda c, n: FakeStore()))
    assert check_store.main() == 1
    out = capsys.readouterr().out
    assert "extra in store 6" in out and "python scripts/sync_docs.py --allow-mass-delete" in out and "One" in out
