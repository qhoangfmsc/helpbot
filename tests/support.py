"""Test doubles shared by the test suites."""

from pathlib import Path

from helpbot.pipeline import LocalDoc, load_local
from helpbot.sync import RemoteDoc
from helpbot.zendesk import Article


class FakeStore:
    """In-memory stand-in for the Gemini store: records every upload/delete call."""

    def __init__(self, docs=None, fail_uploads=()):
        self.docs: list[RemoteDoc] = list(docs or [])
        self.fail_uploads = set(fail_uploads)
        self.calls: list[tuple] = []
        self._n = 0

    @property
    def uploaded_ids(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == "upload"]

    def list_documents(self):
        return list(self.docs)

    def upload(self, path, article_id, content_hash):
        self.calls.append(("upload", article_id))
        if article_id in self.fail_uploads:
            raise RuntimeError("boom")
        self._n += 1
        self.docs.append(RemoteDoc(f"docs/{article_id}-{self._n}", article_id, content_hash))

    def delete(self, document_name):
        self.calls.append(("delete", document_name))
        self.docs = [d for d in self.docs if d.name != document_name]


def make_local(tmp_path: Path, **articles: str) -> dict[str, LocalDoc]:
    files = {}
    for article_id, text in articles.items():
        path = tmp_path / f"{article_id}.md"
        path.write_text(text, encoding="utf-8")
        files[article_id] = path
    return load_local(files)


def make_article(article_id: int | str, title: str | None = None, body: str = "<p>Body</p>", updated_at: str = "2026-01-01T00:00:00Z") -> Article:
    return Article(
        id=str(article_id),
        title=title or f"Article {article_id}",
        html_url=f"https://help.example.com/hc/en-us/articles/{article_id}",
        updated_at=updated_at,
        body_html=body,
    )


def run_main(monkeypatch, tmp_path, store, articles, **env) -> int:
    """Run `main.main()` with the network replaced by `articles` and `store`; env values are strings."""
    import main

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ARTICLES_DIR", str(tmp_path / "out"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(main, "fetch_articles", lambda base_url: iter(articles))
    monkeypatch.setattr(main.genai, "Client", lambda api_key: object())
    monkeypatch.setattr(main.FileSearchStore, "open", lambda client, name: store)
    return main.main()
