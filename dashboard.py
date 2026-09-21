"""Local, read-only newsroom dashboard backed by the linked Neon database."""

import argparse
import os

from flask import Flask, jsonify, render_template, request

from dashboard_data import build_dashboard_payload
from event_store import EventStore


app = Flask(__name__)


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
    return render_template("dashboard.html", data_endpoint="/api/events?limit=5000")


@app.get("/api/events")
def events_api():
    allowed = {
        "q", "company", "department", "source", "min_amount", "max_amount",
        "date_from", "date_to", "has_amount", "sort", "limit",
    }
    filters = {key: request.args.get(key) for key in allowed if request.args.get(key)}
    limit = filters.pop("limit", 5000)
    payload = build_dashboard_payload(
        EventStore.from_env(), filters=filters, limit=limit
    )
    return jsonify(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=int(os.environ.get("CONDUCTOR_PORT", "8000")))
    args = parser.parse_args()
    EventStore.from_env().verify()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
