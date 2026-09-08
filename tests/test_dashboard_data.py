import json
from datetime import date, datetime, timezone
from decimal import Decimal

from dashboard import app
from dashboard_data import build_dashboard_payload, write_public_dashboard


NOW = datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self):
        self.filters = None

    def search_events(self, filters):
        self.filters = filters
        return (
            [
                {
                    "id": 123,
                    "external_id": "private-internal-key",
                    "raw_payload": {"secret": "not public"},
                    "source_name": "USASpending — new awards",
                    "category": "adjacent",
                    "title": "Example award",
                    "link": "https://example.gov/award/1",
                    "summary": "Public source summary",
                    "company_name": "Example Company",
                    "entity_name": None,
                    "department_name": "Department of Energy",
                    "amount_value": Decimal("1250000.50"),
                    "amount_currency": "USD",
                    "amount_type": "award_total",
                    "amount_percentile": Decimal("0.97"),
                    "event_date": date(2026, 8, 26),
                    "published_at": NOW,
                    "first_seen_at": NOW,
                    "last_seen_at": NOW,
                }
            ],
            {
                "sources": ["USASpending — new awards"],
                "companies": ["Example Company"],
                "departments": ["Department of Energy"],
            },
        )


def test_payload_is_serializable_and_exposes_only_public_fields():
    store = FakeStore()
    payload = build_dashboard_payload(store, limit=4321, refreshed_at=NOW)

    assert store.filters == {"limit": 4321}
    assert payload["events"][0]["amount_value"] == 1250000.5
    assert payload["events"][0]["event_date"] == "2026-08-26"
    assert payload["events"][0]["published_at"] == NOW.isoformat()
    assert payload["stats"] == {
        "total": 1,
        "with_amount": 1,
        "largest_amount": 1250000.5,
        "refreshed_at": NOW.isoformat(timespec="seconds"),
    }
    serialized = json.dumps(payload)
    assert "private-internal-key" not in serialized
    assert "raw_payload" not in serialized
    assert '"id": 123' not in serialized


def test_public_build_uses_relative_json_snapshot(tmp_path):
    payload = write_public_dashboard(FakeStore(), output_dir=tmp_path)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    exported = json.loads((tmp_path / "data" / "events.json").read_text())

    assert payload == exported
    assert 'const dataEndpoint = "data/events.json"' in page
    assert "/api/events" not in page
    assert (tmp_path / ".nojekyll").exists()


def test_local_dashboard_uses_local_api():
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b'const dataEndpoint = "/api/events?limit=5000"' in response.data
