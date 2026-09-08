from datetime import datetime, timezone

from event_store import EventStore
from retention import classify_event_date, retention_window


NOW = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)


def test_seven_calendar_date_window():
    window = retention_window(NOW)
    assert window.cutoff.isoformat() == "2026-08-20"
    assert window.today.isoformat() == "2026-08-26"
    assert window.first_seen_start.isoformat() == "2026-08-20T00:00:00+00:00"
    assert window.first_seen_end.isoformat() == "2026-08-27T00:00:00+00:00"


def test_date_boundaries_and_invalid_dates():
    assert classify_event_date("2026-08-20", NOW) == "accepted"
    assert classify_event_date("2026-08-26", NOW) == "accepted"
    assert classify_event_date("2026-08-19", NOW) == "expired"
    assert classify_event_date("2026-08-27", NOW) == "future"
    assert classify_event_date("", NOW) == "undated"


def test_store_reports_rejected_dates_without_opening_database():
    items = [
        {"id": "old", "published": "2009-01-05", "source_name": "test"},
        {"id": "future", "published": "2027-01-01", "source_name": "test"},
    ]
    result = EventStore("unused").store_items(items, observed_at=NOW)
    assert result.received == 2
    assert result.accepted == 0
    assert result.rejected_expired == 1
    assert result.rejected_future == 1
