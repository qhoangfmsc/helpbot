from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import errors, types

from helpbot.store import FileSearchStore, with_retries


def server_error():
    return errors.ServerError(503, {"error": {"message": "overloaded"}})


def client_error(code):
    return errors.ClientError(code, {"error": {"message": "nope"}})


def test_retries_transient_errors_then_succeeds():
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise server_error()
        return "ok"

    assert with_retries(flaky, sleep=sleeps.append) == "ok"
    assert len(calls) == 3 and sleeps == [2.0, 4.0]


def test_rate_limit_is_retried_but_other_client_errors_are_not():
    calls = []

    def rate_limited():
        calls.append(1)
        raise client_error(429)

    with pytest.raises(errors.ClientError):
        with_retries(rate_limited, attempts=3, sleep=lambda s: None)
    assert len(calls) == 3

    calls.clear()

    def forbidden():
        calls.append(1)
        raise client_error(403)

    with pytest.raises(errors.ClientError):
        with_retries(forbidden, sleep=lambda s: None)
    assert len(calls) == 1


def test_gives_up_after_the_configured_attempts():
    calls = []

    def always_down():
        calls.append(1)
        raise server_error()

    with pytest.raises(errors.ServerError):
        with_retries(always_down, attempts=4, sleep=lambda s: None)
    assert len(calls) == 4


class FakeClient:
    def __init__(self, stores=(), documents=(), operations=None):
        self.created = []
        self.deleted = []
        self.uploads = []
        self._operations = list(operations or [])
        self._stores, self._documents = list(stores), list(documents)
        self.file_search_stores = SimpleNamespace(
            list=lambda: iter(self._stores),
            get=lambda name: SimpleNamespace(name=name, display_name="x"),
            create=self._create,
            upload_to_file_search_store=self._upload,
            documents=SimpleNamespace(list=lambda parent: iter(self._documents), delete=self._delete),
        )
        self.operations = SimpleNamespace(get=lambda op: self._operations.pop(0))

    def _create(self, config):
        self.created.append(config)
        return SimpleNamespace(name="fileSearchStores/new", display_name=config["display_name"])

    def _upload(self, file, file_search_store_name, config):
        self.uploads.append((file, file_search_store_name, config))
        return self._operations.pop(0)

    def _delete(self, name, config):
        self.deleted.append((name, config))


def doc(name, state=types.DocumentState.STATE_ACTIVE, **meta):
    return SimpleNamespace(
        name=name, state=state, custom_metadata=[types.CustomMetadata(key=k, string_value=v) for k, v in meta.items()]
    )


def test_open_reuses_a_store_with_the_same_display_name():
    client = FakeClient(stores=[SimpleNamespace(name="fileSearchStores/abc", display_name="helpbot-docs")])
    assert FileSearchStore.open(client, "helpbot-docs").name == "fileSearchStores/abc"
    assert client.created == []


def test_open_creates_the_store_when_missing():
    client = FakeClient()
    assert FileSearchStore.open(client, "helpbot-docs").name == "fileSearchStores/new"
    assert client.created == [{"display_name": "helpbot-docs"}]


def test_open_accepts_a_resource_name():
    assert FileSearchStore.open(FakeClient(), "fileSearchStores/xyz").name == "fileSearchStores/xyz"


def test_list_documents_returns_only_active_documents_with_our_metadata():
    client = FakeClient(documents=[
        doc("d/1", article_id="1", content_hash="h1"),
        doc("d/2", article_id="2"),  # no hash
        doc("d/3"),  # foreign document
        doc("d/4", state=types.DocumentState.STATE_PENDING, article_id="4", content_hash="h4"),
    ])
    docs = FileSearchStore(client, "fileSearchStores/s").list_documents()
    assert [(d.name, d.article_id, d.content_hash) for d in docs] == [("d/1", "1", "h1")]


def test_upload_sends_metadata_and_chunking_and_waits_for_indexing():
    pending, done = SimpleNamespace(done=False, error=None), SimpleNamespace(done=True, error=None)
    client = FakeClient(operations=[pending, done])
    sleeps = []
    FileSearchStore(client, "fileSearchStores/s", sleep=sleeps.append).upload(Path("x/1-a.md"), "1", "h1")
    file, store, config = client.uploads[0]
    assert (file, store) == ("x/1-a.md", "fileSearchStores/s")
    assert {m.key: m.string_value for m in config.custom_metadata} == {"article_id": "1", "content_hash": "h1"}
    assert config.chunking_config.white_space_config.max_tokens_per_chunk == 400
    assert config.chunking_config.white_space_config.max_overlap_tokens == 50
    assert config.display_name == "1-a.md" and len(sleeps) == 1


def test_upload_raises_when_indexing_fails():
    client = FakeClient(operations=[SimpleNamespace(done=True, error={"message": "bad file"})])
    with pytest.raises(RuntimeError, match="bad file"):
        FileSearchStore(client, "fileSearchStores/s").upload(Path("1-a.md"), "1", "h1")


def test_delete_forces_removal_of_non_empty_documents():
    client = FakeClient()
    FileSearchStore(client, "fileSearchStores/s").delete("fileSearchStores/s/documents/1")
    assert client.deleted == [("fileSearchStores/s/documents/1", {"force": True})]
