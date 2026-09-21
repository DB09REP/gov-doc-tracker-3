"""Shared seven-day UTC retention policy for stored government events."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from dates import parse_date


RETENTION_DAYS = 7


@dataclass(frozen=True)
class RetentionWindow:
    cutoff: date
    today: date

    @property
    def first_seen_start(self):
        return datetime.combine(self.cutoff, time.min, tzinfo=timezone.utc)

    @property
    def first_seen_end(self):
        return datetime.combine(
            self.today + timedelta(days=1), time.min, tzinfo=timezone.utc
        )


def utc_today(now=None):
    """Return the UTC calendar date used by ingestion and database queries."""
    now = now or datetime.now(timezone.utc)
    if isinstance(now, date) and not isinstance(now, datetime):
        return now
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).date()


def retention_window(now=None):
    """Today plus the preceding six UTC dates."""
    today = utc_today(now)
    return RetentionWindow(
        cutoff=today - timedelta(days=RETENTION_DAYS - 1),
        today=today,
    )


def classify_event_date(value, now=None):
    """Classify a source event date as accepted, undated, expired, or future."""
    parsed = parse_date(value)
    if parsed is None:
        return "undated"
    window = retention_window(now)
    event_date = parsed.date()
    if event_date < window.cutoff:
        return "expired"
    if event_date > window.today:
        return "future"
    return "accepted"


def retained_sql(alias=""):
    """Return a parameterized SQL predicate matching the shared policy."""
    prefix = f"{alias}." if alias else ""
    return (
        f"(({prefix}event_date BETWEEN %s AND %s) OR "
        f"({prefix}event_date IS NULL AND {prefix}first_seen_at >= %s "
        f"AND {prefix}first_seen_at < %s))"
    )


def retained_parameters(now=None):
    window = retention_window(now)
    return (
        window.cutoff,
        window.today,
        window.first_seen_start,
        window.first_seen_end,
    )
