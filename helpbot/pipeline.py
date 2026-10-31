"""Scrape -> delta -> upload: the daily job's logic, independent of how it is configured."""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from helpbot.chunking import estimate_chunks
from helpbot.scrape import latest, write_articles
from helpbot.sync import Delta, RemoteDoc, content_hash, plan_delta
from helpbot.zendesk import Article

log = logging.getLogger(__name__)

MAX_ORPHAN_FRACTION = 0.5  # deleting more than this share of the store looks like a broken fetch, not real deletions


class Store(Protocol):
    def list_documents(self) -> list[RemoteDoc]: ...
    def upload(self, path: Path, article_id: str, content_hash: str) -> None: ...
    def delete(self, document_name: str) -> None: ...


@dataclass(frozen=True)
class LocalDoc:
    path: Path
    hash: str
    chunks: int


@dataclass
class Summary:
    added: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    files: int = 0  # uploaded (embedded) this run
    chunks: int = 0  # estimated, see helpbot.chunking
    store_documents: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0 and not self.problems

    def line(self) -> str:
        return (
            f"added={self.added} updated={self.updated} skipped={self.skipped} deleted={self.deleted} "
            f"failed={self.failed} files={self.files} chunks_estimated={self.chunks} store_documents={self.store_documents}"
        )


def load_local(files: dict[str, Path]) -> dict[str, LocalDoc]:
    local = {}
    for article_id, path in files.items():
        text = path.read_text(encoding="utf-8")
        local[article_id] = LocalDoc(path, content_hash(text), estimate_chunks(text))
    return local


def run_job(articles: list[Article], out_dir: Path, store: Store, workers: int = 4, limit: int | None = None) -> Summary:
    """One daily run on already-fetched articles: write Markdown, compare with the store, upload only the delta.

    `limit` keeps only the N most recently updated articles (partial run: nothing is ever deleted then).
    """
    selected = latest(articles, limit) if limit else articles
    files = write_articles(selected, out_dir)
    return sync_store(load_local(files), store, workers=workers, allow_delete=limit is None)


def sync_store(local: dict[str, LocalDoc], store: Store, workers: int = 4, allow_delete: bool = True) -> Summary:
    summary = Summary()
    remote = store.list_documents()
    delta = plan_delta({i: d.hash for i, d in local.items()}, remote)
    summary.skipped = len(delta.skipped)
    log.info(
        "plan add=%s update=%s skip=%s orphans=%s duplicates=%s (store has %s documents)",
        len(delta.added), len(delta.updated), len(delta.skipped), len(delta.orphans), len(delta.duplicates), len(remote),
    )

    def upload_one(article_id: str) -> bool:
        doc = local[article_id]
        try:
            store.upload(doc.path, article_id, doc.hash)
        except Exception:
            log.exception("upload failed article_id=%s", article_id)
            return False
        log.info("uploaded article_id=%s chunks_estimated=%s", article_id, doc.chunks)
        return True

    todo = delta.added + delta.updated
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        results = dict(zip(todo, pool.map(upload_one, todo)))
    added, updated = set(delta.added), set(delta.updated)
    for article_id, uploaded in results.items():  # single-threaded from here on: counters are not thread-safe
        if not uploaded:
            summary.failed += 1  # a failed update keeps its old version in the store; the next run retries
            continue
        summary.added += article_id in added
        summary.updated += article_id in updated
        summary.files += 1
        summary.chunks += local[article_id].chunks
        for old in delta.replaced.get(article_id, []):  # only now that the new version is indexed
            _delete(store, old, summary)

    for duplicate in delta.duplicates:
        _delete(store, duplicate, summary)
    _delete_orphans(delta, len(remote), store, summary, allow_delete)
    summary.store_documents = len(store.list_documents())
    return summary


def _delete(store: Store, doc: RemoteDoc, summary: Summary) -> None:
    try:
        store.delete(doc.name)
        summary.deleted += 1
    except Exception:
        log.exception("delete failed document=%s (a duplicate is harmless, the next run removes it)", doc.name)


def _delete_orphans(delta: Delta, remote_count: int, store: Store, summary: Summary, allow_delete: bool) -> None:
    if not delta.orphans:
        return
    if not allow_delete:
        log.warning("not deleting %s documents of articles missing from this run (partial run)", len(delta.orphans))
        return
    if len(delta.orphans) > MAX_ORPHAN_FRACTION * remote_count:
        summary.problems.append(f"refused to delete {len(delta.orphans)} of {remote_count} documents (fetch looks incomplete)")
        log.error(summary.problems[-1])
        return
    for orphan in delta.orphans:
        _delete(store, orphan, summary)
