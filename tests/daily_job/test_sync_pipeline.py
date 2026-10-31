from helpbot.pipeline import sync_store
from helpbot.sync import RemoteDoc, content_hash
from tests.support import FakeStore, make_local


def test_first_run_adds_everything_second_run_skips_everything(tmp_path):
    local = make_local(tmp_path, a="alpha", b="beta " * 2000)
    store = FakeStore()
    first = sync_store(local, store, workers=2)
    assert (first.added, first.updated, first.skipped, first.failed) == (2, 0, 0, 0)
    assert first.files == 2 and first.chunks == local["a"].chunks + local["b"].chunks and first.chunks > 2
    assert first.store_documents == 2 and first.ok

    store.calls.clear()
    second = sync_store(local, store, workers=2)
    assert (second.added, second.updated, second.skipped) == (0, 0, 2)
    assert store.calls == [] and second.files == 0 and second.ok


def test_changed_article_uploads_new_version_before_deleting_the_old_one(tmp_path):
    store = FakeStore()
    sync_store(make_local(tmp_path, a="v1", b="b"), store)
    store.calls.clear()
    summary = sync_store(make_local(tmp_path, a="v2", b="b"), store)
    assert (summary.added, summary.updated, summary.skipped) == (0, 1, 1)
    assert [c[0] for c in store.calls] == ["upload", "delete"]
    assert sorted(d.article_id for d in store.docs) == ["a", "b"]
    assert {d.content_hash for d in store.docs if d.article_id == "a"} == {content_hash("v2")}


def test_failed_update_keeps_the_old_version_and_fails_the_run(tmp_path):
    store = FakeStore()
    sync_store(make_local(tmp_path, a="v1"), store)
    store.fail_uploads = {"a"}
    summary = sync_store(make_local(tmp_path, a="v2"), store)
    assert summary.failed == 1 and summary.updated == 0 and not summary.ok
    assert [d.content_hash for d in store.docs] == [content_hash("v1")]  # nothing lost


def test_one_failed_upload_does_not_stop_the_others(tmp_path):
    store = FakeStore(fail_uploads={"a"})
    summary = sync_store(make_local(tmp_path, a="a", b="b", c="c"), store, workers=3)
    assert (summary.added, summary.failed) == (2, 1) and not summary.ok


def test_articles_removed_from_the_site_are_deleted(tmp_path):
    store = FakeStore()
    sync_store(make_local(tmp_path, a="a", b="b", c="c"), store)
    summary = sync_store(make_local(tmp_path, a="a", b="b"), store)
    assert summary.deleted == 1 and summary.ok
    assert sorted(d.article_id for d in store.docs) == ["a", "b"]


def test_mass_deletion_is_refused_because_it_looks_like_a_broken_fetch(tmp_path):
    store = FakeStore()
    sync_store(make_local(tmp_path, a="a", b="b", c="c", d="d"), store)
    summary = sync_store(make_local(tmp_path, a="a"), store)
    assert summary.deleted == 0 and not summary.ok and "refused to delete 3 of 4" in summary.problems[0]
    assert len(store.docs) == 4


def test_partial_runs_never_delete(tmp_path):
    store = FakeStore()
    sync_store(make_local(tmp_path, a="a", b="b"), store)
    summary = sync_store(make_local(tmp_path, a="a"), store, allow_delete=False)
    assert summary.deleted == 0 and summary.ok and len(store.docs) == 2


def test_duplicate_left_by_an_interrupted_update_is_cleaned_up(tmp_path):
    local = make_local(tmp_path, a="v2")
    store = FakeStore([RemoteDoc("docs/old", "a", content_hash("v1")), RemoteDoc("docs/new", "a", content_hash("v2"))])
    summary = sync_store(local, store)
    assert summary.skipped == 1 and summary.deleted == 1
    assert [d.name for d in store.docs] == ["docs/new"]


def test_summary_line_has_the_counters_the_job_must_log(tmp_path):
    line = sync_store(make_local(tmp_path, a="a"), FakeStore()).line()
    for key in ("added=1", "updated=0", "skipped=0", "deleted=0", "failed=0", "files=1", "chunks_estimated=1", "store_documents=1"):
        assert key in line
