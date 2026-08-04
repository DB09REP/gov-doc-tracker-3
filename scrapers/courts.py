"""Federal court filings via CourtListener's RECAP search.

Free API, no key strictly required but a token raises your rate limit —
get one at https://www.courtlistener.com/help/api/rest/ and set it as
the COURTLISTENER_TOKEN secret.

This pulls recently-filed RECAP documents system-wide. For a beat-specific
feed, narrow with a `q` keyword (company/person name) — see the `QUERY`
constant below.
"""
import os
import sys
from datetime import date, datetime, timedelta
from .http import get

CATEGORY = "courts"
SOURCE_NAME = "CourtListener — new RECAP filings"
BASE = "https://www.courtlistener.com/api/rest/v4"

# Optional: narrow to a keyword (e.g. a company or person you're tracking).
# Leave as "" to pull the general recent-filings firehose.
QUERY = os.environ.get("COURTLISTENER_QUERY", "")

# `dateFiled` on some dockets (notably bankruptcy misc. entries) is an
# unreliable/placeholder value and can come back decades in the future.
# Anything past this cutoff is treated as "no reliable date" rather than
# trusted and sorted on.
_MAX_PLAUSIBLE_DATE = date.today() + timedelta(days=7)


def _sane_date(value):
    if not value:
        return ""
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return ""
    if d > _MAX_PLAUSIBLE_DATE:
        return ""  # implausible — drop it rather than trust it
    return value


def fetch_items(page_size=40):
    token = (os.environ.get("COURTLISTENER_TOKEN") or "").strip() or None
    headers = {"Authorization": f"Token {token}"} if token else {}
    url = f"{BASE}/search/"
    params = {
        "type": "r",  # RECAP documents
        # Sort by when CourtListener/RECAP actually ingested the filing,
        # not the docket's self-reported dateFiled — the latter is what
        # produced the bogus far-future dates.
        "order_by": "dateFiled desc",
    }
    if QUERY:
        params["q"] = QUERY
    try:
        resp = get(url, params=params, headers=headers)
    except Exception as exc:
        print(f"[detail] CourtListener/RECAP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for r in data.get("results", [])[:page_size]:
        case_name = r.get("caseName") or "Unknown case"
        court = r.get("court", "")
        date_filed = _sane_date(r.get("dateFiled", ""))
        docket_id = r.get("docket_id")
        link = f"https://www.courtlistener.com/docket/{docket_id}/" if docket_id else "https://www.courtlistener.com/"
        summary = f"New RECAP activity in {case_name}, filed {date_filed}." if date_filed else f"New RECAP activity in {case_name} (filing date unavailable)."
        items.append({
            "id": f"cl-{docket_id}-{r.get('dateFiled', '')}",
            "title": f"{case_name} ({court})",
            "link": link,
            "summary": summary,
            "published": date_filed,  # empty string sorts to "now" in build_feeds, which is a safe default
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
        })
    return items
