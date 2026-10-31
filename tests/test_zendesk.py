from helpbot.zendesk import fetch_articles


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return FakeResponse(self.pages[len(self.calls) - 1])


def raw(id, **overrides):
    return {"id": id, "title": f" T{id} ", "html_url": f"https://h/{id}", "updated_at": "2026-01-01T00:00:00Z",
            "body": "<p>x</p>", "draft": False, **overrides}


def test_follows_next_page_and_skips_drafts_and_empty_bodies():
    session = FakeSession([
        {"page": 1, "page_count": 2, "count": 4, "next_page": "https://h/next",
         "articles": [raw(1), raw(2, draft=True)]},
        {"page": 2, "page_count": 2, "count": 4, "next_page": None,
         "articles": [raw(3, body=""), raw(4)]},
    ])
    articles = list(fetch_articles(base_url="https://h", session=session))
    assert [a.id for a in articles] == ["1", "4"]
    assert articles[0].title == "T1"
    assert session.calls[0][1] == {"per_page": 100}
    assert session.calls[1] == ("https://h/next", None)
