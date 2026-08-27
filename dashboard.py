"""Local, read-only newsroom dashboard backed by the linked Neon database."""

import argparse
import os
from datetime import date, datetime
from decimal import Decimal

from flask import Flask, jsonify, render_template, request

from event_store import EventStore


app = Flask(__name__)


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@app.after_request
def secure_local_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:"
    )
    return response


@app.get("/")
def index():
    return render_template("dashboard.html")


@app.get("/api/events")
def events_api():
    allowed = {
        "q", "company", "department", "source", "min_amount", "max_amount",
        "date_from", "date_to", "has_amount", "sort", "limit",
    }
    filters = {key: request.args.get(key) for key in allowed if request.args.get(key)}
    rows, facets = EventStore.from_env().search_events(filters)
    events = [{key: _json_value(value) for key, value in row.items()} for row in rows]
    amounts = [row["amount_value"] for row in rows if row["amount_value"] is not None]
    return jsonify(
        {
            "events": events,
            "facets": {
                "sources": facets["sources"] or [],
                "companies": facets["companies"] or [],
                "departments": facets["departments"] or [],
            },
            "stats": {
                "shown": len(events),
                "with_amount": len(amounts),
                "largest_amount": _json_value(max(amounts)) if amounts else None,
                "refreshed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=int(os.environ.get("CONDUCTOR_PORT", "8000")))
    args = parser.parse_args()
    EventStore.from_env().verify()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
