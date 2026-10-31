"""Decide what to upload and what to delete. Pure functions, no I/O."""

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping


def content_hash(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RemoteDoc:
    """A document already in the store, identified by the metadata we attached when uploading it."""

    name: str
    article_id: str
    content_hash: str


@dataclass
class Delta:
    added: list[str] = field(default_factory=list)  # article ids not in the store yet
    updated: list[str] = field(default_factory=list)  # in the store with a different hash
    skipped: list[str] = field(default_factory=list)  # in the store with the same hash
    replaced: dict[str, list[RemoteDoc]] = field(default_factory=dict)  # old versions, delete AFTER the new upload worked
    duplicates: list[RemoteDoc] = field(default_factory=list)  # extra copies of an up-to-date article
    orphans: list[RemoteDoc] = field(default_factory=list)  # articles that no longer exist on the site


def plan_delta(local: Mapping[str, str], remote: Iterable[RemoteDoc]) -> Delta:
    """`local` maps article id -> content hash of the freshly scraped Markdown.

    A crash between "upload new version" and "delete old version" leaves two documents for one article; the next
    run sees the up-to-date one (skipped) and removes the other (duplicates), so runs converge.
    """
    by_article: dict[str, list[RemoteDoc]] = defaultdict(list)
    for doc in remote:
        by_article[doc.article_id].append(doc)

    delta = Delta()
    for article_id, new_hash in sorted(local.items()):
        docs = by_article.get(article_id, [])
        current = next((d for d in docs if d.content_hash == new_hash), None)
        if not docs:
            delta.added.append(article_id)
        elif current is None:
            delta.updated.append(article_id)
            delta.replaced[article_id] = docs
        else:
            delta.skipped.append(article_id)
            delta.duplicates.extend(d for d in docs if d.name != current.name)
    delta.orphans = [d for article_id, docs in sorted(by_article.items()) if article_id not in local for d in docs]
    return delta
