"""Date normalization shared by feed generation and durable storage."""

from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime


def parse_date(value):
    """Return a timezone-aware datetime, or ``None`` when parsing fails.

    Government APIs in this project return a mix of ISO 8601, compact SEC
    dates, RFC 2822 timestamps, and occasionally Unix timestamps. An invalid
    value must not be converted to "now": doing that makes old records appear
    new on every poll.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    else:
        text = str(value).strip()
        if not text:
            return None

        if text.isdigit():
            if len(text) == 8:
                try:
                    dt = datetime.strptime(text, "%Y%m%d")
                except ValueError:
                    return None
            elif len(text) in (10, 13):
                timestamp = int(text) / (1000 if len(text) == 13 else 1)
                try:
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                except (OverflowError, OSError, ValueError):
                    return None
            else:
                return None
        else:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                try:
                    dt = parsedate_to_datetime(text)
                except (TypeError, ValueError, OverflowError):
                    return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
