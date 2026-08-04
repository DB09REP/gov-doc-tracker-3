import sys
"""USASpending — recently posted federal contract & grant awards.
No API key needed. Uses the spending_by_award search endpoint.
"""
from datetime import date, timedelta
import json
from .http import _session, polite_sleep

CATEGORY = "adjacent"
SOURCE_NAME = "USASpending — new awards"
URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def fetch_items(days_back=3, limit=40):
    since = (date.today() - timedelta(days=days_back)).isoformat()
    today = date.today().isoformat()
    payload = {
        "filters": {
            "time_period": [{"start_date": since, "end_date": today}],
            "award_type_codes": ["A", "B", "C", "D"],  # contracts
        },
        "fields": ["Award ID", "Recipient Name", "Awarding Agency", "Start Date", "Award Amount", "generated_internal_id"],
        "sort": "Start Date",
        "order": "desc",
        "limit": limit,
        "page": 1,
    }
    try:
        resp = _session.post(URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[detail] USASpending awards: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []
    polite_sleep(0.3)

    data = resp.json()
    items = []
    for r in data.get("results", []):
        award_id = r.get("Award ID", "")
        recipient = r.get("Recipient Name", "Unknown recipient")
        agency = r.get("Awarding Agency", "")
        start = r.get("Start Date", "")
        amount = r.get("Award Amount", "")
        internal_id = r.get("generated_internal_id", award_id)
        link = f"https://www.usaspending.gov/award/{internal_id}"
        items.append({
            "id": f"usaspending-{internal_id}",
            "title": f"{recipient} — {agency} (${amount})",
            "link": link,
            "summary": f"Award {award_id} to {recipient} from {agency}, starting {start}.",
            "published": start,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
        })
    return items
