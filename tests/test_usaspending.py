import json

from scrapers import usaspending


class FakeResponse:
    def __init__(self, results):
        self.results = results

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": self.results}


def _award(internal_id, agency, recipient):
    return {
        "Award ID": f"award-{internal_id}",
        "Recipient Name": recipient,
        "Awarding Agency": agency,
        "Base Obligation Date": "2026-09-21",
        "Last Modified Date": "2026-09-21 14:30:00",
        "Award Amount": 10_000_000,
        "Description": "Example award",
        "generated_internal_id": internal_id,
    }


def test_fetches_defense_slice_and_deduplicates_overlapping_awards(monkeypatch):
    calls = []
    shared = _award("shared", "Department of Defense", "Shared contractor")

    def fake_post(url, data, headers, timeout):
        payload = json.loads(data)
        calls.append(payload)
        agencies = payload["filters"].get("agencies")
        if agencies:
            return FakeResponse(
                [shared, _award("dod-only", "Department of Defense", "Defense Co")]
            )
        return FakeResponse(
            [shared, _award("civilian", "Department of Energy", "Energy Co")]
        )

    monkeypatch.setattr(usaspending._session, "post", fake_post)
    monkeypatch.setattr(usaspending, "polite_sleep", lambda _seconds: None)

    items = usaspending.fetch_items(days_back=6, limit=100)

    assert len(calls) == 2
    assert calls[0]["limit"] == 100
    assert calls[0]["sort"] == "Last Modified Date"
    assert "agencies" not in calls[0]["filters"]
    assert calls[1]["filters"]["agencies"] == [
        {
            "type": "awarding",
            "tier": "toptier",
            "name": "Department of Defense",
        }
    ]
    assert {item["id"] for item in items} == {
        "usaspending-shared",
        "usaspending-civilian",
        "usaspending-dod-only",
    }
    assert any(
        item["department_name"] == "Department of Defense" for item in items
    )
    assert all(item["event_date"] == "2026-09-21 14:30:00" for item in items)
