from scrapers import doj


class _Response:
    def json(self):
        return {"results": []}


def test_doj_requests_newest_releases(monkeypatch):
    captured = {}

    def fake_get(url, params):
        captured.update({"url": url, "params": params})
        return _Response()

    monkeypatch.setattr(doj, "get", fake_get)
    assert doj.fetch_items(page_size=12) == []
    assert captured["params"] == {
        "pagesize": 12,
        "sort": "created",
        "direction": "DESC",
    }
