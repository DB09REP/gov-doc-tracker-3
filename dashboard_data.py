"""Build the browser-safe dataset and shared dashboard page."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).parent
TEMPLATE_DIR = ROOT / "templates"
PUBLIC_EVENT_FIELDS = (
    "source_name",
    "category",
    "title",
    "link",
    "summary",
    "company_name",
    "entity_name",
    "department_name",
    "amount_value",
    "amount_currency",
    "amount_type",
    "amount_percentile",
    "event_date",
    "published_at",
)


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def build_dashboard_payload(store, *, filters=None, limit=5000, refreshed_at=None):
    """Return a deliberately limited public view of retained Neon events."""
    filters = dict(filters or {})
    filters["limit"] = limit
    rows, facets = store.search_events(filters)
    events = [
        {field: json_value(row.get(field)) for field in PUBLIC_EVENT_FIELDS}
        for row in rows
    ]
    amounts = [event["amount_value"] for event in events if event["amount_value"] is not None]
    refreshed_at = refreshed_at or datetime.now(timezone.utc)
    return {
        "events": events,
        "facets": {
            "sources": facets.get("sources") or [],
            "companies": facets.get("companies") or [],
            "departments": facets.get("departments") or [],
        },
        "stats": {
            "total": len(events),
            "with_amount": len(amounts),
            "largest_amount": max(amounts) if amounts else None,
            "refreshed_at": refreshed_at.isoformat(timespec="seconds"),
        },
    }


def render_dashboard(*, data_endpoint):
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
    )
    return environment.get_template("dashboard.html").render(
        data_endpoint=data_endpoint
    )


def write_public_dashboard(store, *, output_dir=None, limit=5000):
    """Export a static Pages dashboard without exposing database access."""
    output_dir = Path(output_dir or ROOT / "docs")
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_dashboard_payload(store, limit=limit)
    (data_dir / "events.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (output_dir / "index.html").write_text(
        render_dashboard(data_endpoint="data/events.json"),
        encoding="utf-8",
    )
    (output_dir / ".nojekyll").touch()
    print(f"wrote {data_dir / 'events.json'} ({len(payload['events'])} events)")
    print(f"wrote {output_dir / 'index.html'}")
    return payload
