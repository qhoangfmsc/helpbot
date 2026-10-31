from helpbot.sync import RemoteDoc, content_hash, plan_delta


def doc(article_id, hash_, name=None):
    return RemoteDoc(name=name or f"docs/{article_id}-{hash_}", article_id=article_id, content_hash=hash_)


def test_content_hash_is_stable_and_sensitive():
    assert content_hash("a") == content_hash("a")
    assert content_hash("a") != content_hash("b")
    assert len(content_hash("a")) == 64


def test_first_run_everything_is_added():
    delta = plan_delta({"1": "h1", "2": "h2"}, [])
    assert delta.added == ["1", "2"] and not delta.updated and not delta.skipped


def test_second_run_with_no_change_skips_everything():
    delta = plan_delta({"1": "h1", "2": "h2"}, [doc("1", "h1"), doc("2", "h2")])
    assert delta.skipped == ["1", "2"] and not delta.added and not delta.updated
    assert not delta.replaced and not delta.duplicates and not delta.orphans


def test_changed_article_is_updated_and_old_version_is_marked_for_replacement():
    old = doc("2", "old")
    delta = plan_delta({"1": "h1", "2": "new"}, [doc("1", "h1"), old])
    assert delta.updated == ["2"] and delta.skipped == ["1"]
    assert delta.replaced == {"2": [old]}


def test_new_article_alongside_existing_ones():
    delta = plan_delta({"1": "h1", "3": "h3"}, [doc("1", "h1")])
    assert delta.added == ["3"] and delta.skipped == ["1"]


def test_article_removed_from_the_site_becomes_an_orphan():
    gone = doc("9", "h9")
    delta = plan_delta({"1": "h1"}, [doc("1", "h1"), gone])
    assert delta.orphans == [gone]


def test_interrupted_update_converges_on_the_next_run():
    # previous run uploaded the new version but crashed before deleting the old one
    old, new = doc("1", "old"), doc("1", "new")
    delta = plan_delta({"1": "new"}, [old, new])
    assert delta.skipped == ["1"] and not delta.updated
    assert delta.duplicates == [old]


def test_results_are_ordered_by_article_id_so_runs_are_reproducible():
    delta = plan_delta({"b": "1", "a": "1", "c": "1"}, [])
    assert delta.added == ["a", "b", "c"]
