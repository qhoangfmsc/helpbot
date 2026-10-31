"""The daily-job contract: re-scrape, detect new/updated, upload ONLY the delta, log added/updated/skipped."""

from helpbot.pipeline import run_job
from tests.support import FakeStore, make_article


def articles(n: int, **overrides):
    return [make_article(i, updated_at=f"2026-01-{i:02d}T00:00:00Z", **overrides) for i in range(1, n + 1)]


def run(store, tmp_path, items, limit=None):
    return run_job(items, tmp_path / "out", store, workers=2, limit=limit)


def test_first_run_uploads_everything(tmp_path):
    store = FakeStore()
    summary = run(store, tmp_path, articles(30))
    assert (summary.added, summary.updated, summary.skipped) == (30, 0, 0)
    assert len(store.docs) == 30


def test_existing_articles_are_skipped_and_only_new_ones_are_uploaded(tmp_path):
    store = FakeStore()
    existing = articles(30)
    run(store, tmp_path, existing)
    store.calls.clear()

    summary = run(store, tmp_path, existing + [make_article(31), make_article(32)])

    assert (summary.added, summary.updated, summary.skipped) == (2, 0, 30)
    assert sorted(store.uploaded_ids) == ["31", "32"]  # nothing else was sent
    assert [c for c in store.calls if c[0] == "delete"] == []


def test_a_rerun_with_no_changes_uploads_nothing(tmp_path):
    store = FakeStore()
    items = articles(30)
    run(store, tmp_path, items)
    store.calls.clear()
    summary = run(store, tmp_path, items)
    assert (summary.added, summary.updated, summary.skipped) == (0, 0, 30)
    assert store.calls == []


def test_only_the_edited_article_is_uploaded_again(tmp_path):
    store = FakeStore()
    items = articles(30)
    run(store, tmp_path, items)
    store.calls.clear()
    items[4] = make_article(5, updated_at="2026-02-01T00:00:00Z", body="<p>Edited text</p>")

    summary = run(store, tmp_path, items)

    assert (summary.added, summary.updated, summary.skipped) == (0, 1, 29)
    assert store.uploaded_ids == ["5"]
    assert len(store.docs) == 30  # the old version was replaced, not duplicated


def test_changing_only_the_timestamp_is_not_an_update(tmp_path):
    store = FakeStore()
    run(store, tmp_path, [make_article(1, updated_at="2026-01-01T00:00:00Z")])
    store.calls.clear()
    summary = run(store, tmp_path, [make_article(1, updated_at="2026-09-09T00:00:00Z")])
    assert (summary.updated, summary.skipped) == (0, 1) and store.calls == []


def test_newest_n_mode_adds_only_what_the_window_newly_covers(tmp_path):
    store = FakeStore()
    items = articles(50)
    first = run(store, tmp_path, items, limit=35)  # ids 16..50
    assert first.added == 35
    store.calls.clear()

    second = run(store, tmp_path, items, limit=40)  # ids 11..50: five more

    assert (second.added, second.skipped) == (5, 35)
    assert sorted(store.uploaded_ids, key=int) == ["11", "12", "13", "14", "15"]


def test_newest_n_mode_never_deletes_what_fell_out_of_the_window(tmp_path):
    store = FakeStore()
    items = articles(40)
    run(store, tmp_path, items, limit=40)
    items.append(make_article(41, updated_at="2026-03-01T00:00:00Z"))  # a brand-new article

    summary = run(store, tmp_path, items, limit=40)  # window slides: id 1 drops out

    assert summary.added == 1 and summary.deleted == 0
    assert len(store.docs) == 41


def test_full_mode_removes_articles_that_disappeared_from_the_site(tmp_path):
    store = FakeStore()
    items = articles(30)
    run(store, tmp_path, items)
    summary = run(store, tmp_path, items[:-1])
    assert summary.deleted == 1 and len(store.docs) == 29
