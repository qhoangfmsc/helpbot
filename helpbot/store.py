"""Gemini File Search store: the only module that talks to the Gemini API."""

import logging
import time
from pathlib import Path
from typing import Callable, TypeVar

from google import genai
from google.genai import errors, types

from helpbot.chunking import MAX_TOKENS_PER_CHUNK, OVERLAP_TOKENS
from helpbot.sync import RemoteDoc

log = logging.getLogger(__name__)

T = TypeVar("T")
DEFAULT_STORE_NAME = "helpbot-docs"
ARTICLE_ID_KEY = "article_id"
CONTENT_HASH_KEY = "content_hash"
UPLOAD_TIMEOUT_SECONDS = 300
POLL_SECONDS = 2.0


def _is_transient(error: Exception) -> bool:
    return isinstance(error, errors.ServerError) or (isinstance(error, errors.ClientError) and error.code == 429)


def with_retries(call: Callable[[], T], attempts: int = 5, base_delay: float = 2.0, sleep=time.sleep) -> T:
    """Retry 5xx / 429 with exponential backoff (2, 4, 8, 16 s); anything else is raised immediately."""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as error:
            if attempt == attempts or not _is_transient(error):
                raise
            delay = min(base_delay * 2 ** (attempt - 1), 60.0)
            log.warning("transient API error (%s), retry %s/%s in %.0fs", error, attempt, attempts - 1, delay)
            sleep(delay)
    raise AssertionError("unreachable")


class FileSearchStore:
    def __init__(self, client: genai.Client, name: str, sleep=time.sleep):
        self.client = client
        self.name = name  # resource name: fileSearchStores/<id>
        self._sleep = sleep

    @classmethod
    def open(cls, client: genai.Client, store: str = DEFAULT_STORE_NAME) -> "FileSearchStore":
        """`store` is a resource name (`fileSearchStores/...`) or a display name that is found or created."""
        if store.startswith("fileSearchStores/"):
            return cls(client, with_retries(lambda: client.file_search_stores.get(name=store)).name)
        for existing in with_retries(lambda: list(client.file_search_stores.list())):
            if existing.display_name == store:
                log.info("using store %s (%s)", store, existing.name)
                return cls(client, existing.name)
        created = with_retries(lambda: client.file_search_stores.create(config={"display_name": store}))
        log.info("created store %s (%s)", store, created.name)
        return cls(client, created.name)

    def list_documents(self) -> list[RemoteDoc]:
        """Active documents that carry our metadata. Others (foreign, failed, pending) are ignored."""
        docs = with_retries(lambda: list(self.client.file_search_stores.documents.list(parent=self.name)))
        found, ignored = [], 0
        for doc in docs:
            meta = {m.key: m.string_value for m in (doc.custom_metadata or [])}
            active = str(getattr(doc.state, "value", doc.state)) == "STATE_ACTIVE"
            if active and meta.get(ARTICLE_ID_KEY) and meta.get(CONTENT_HASH_KEY):
                found.append(RemoteDoc(doc.name, meta[ARTICLE_ID_KEY], meta[CONTENT_HASH_KEY]))
            else:
                ignored += 1
        if ignored:
            log.warning("ignored %s store documents without our metadata or not active", ignored)
        return found

    def upload(self, path: Path, article_id: str, content_hash: str) -> None:
        """Upload one Markdown file with its metadata; returns once it is indexed (raises otherwise)."""
        config = types.UploadToFileSearchStoreConfig(
            display_name=path.name,
            mime_type="text/markdown",
            custom_metadata=[
                types.CustomMetadata(key=ARTICLE_ID_KEY, string_value=article_id),
                types.CustomMetadata(key=CONTENT_HASH_KEY, string_value=content_hash),
            ],
            chunking_config=types.ChunkingConfig(
                white_space_config=types.WhiteSpaceConfig(
                    max_tokens_per_chunk=MAX_TOKENS_PER_CHUNK, max_overlap_tokens=OVERLAP_TOKENS
                )
            ),
        )
        operation = with_retries(
            lambda: self.client.file_search_stores.upload_to_file_search_store(
                file=str(path), file_search_store_name=self.name, config=config
            )
        )
        deadline = time.monotonic() + UPLOAD_TIMEOUT_SECONDS
        while not operation.done:
            if time.monotonic() > deadline:
                raise TimeoutError(f"indexing {path.name} did not finish in {UPLOAD_TIMEOUT_SECONDS}s")
            self._sleep(POLL_SECONDS)
            operation = with_retries(lambda: self.client.operations.get(operation))
        if operation.error:
            raise RuntimeError(f"indexing {path.name} failed: {operation.error}")

    def delete(self, document_name: str) -> None:
        with_retries(
            lambda: self.client.file_search_stores.documents.delete(name=document_name, config={"force": True})
        )
