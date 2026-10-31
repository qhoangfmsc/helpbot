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


def test_text_report_lists_every_article_with_its_status(tmp_path):
    local = make_local(tmp_path, **{"1": "one", "3": "three"})
    report = check_store.build_report(local, [remote("1", "one"), remote("9", "gone")])
    text = check_store.format_report(report, local, listing=True)
    assert "in sync: 1 | missing in store: 1" in text
    assert "MISSING in store" in text and "EXTRA in store" in text and "1.md" in text


def test_summary_only_mode_names_the_problem_articles(tmp_path):
    local = make_local(tmp_path, **{"1": "one"})
    text = check_store.format_report(check_store.build_report(local, []), local, listing=False)
    assert "missing: 1" in text
