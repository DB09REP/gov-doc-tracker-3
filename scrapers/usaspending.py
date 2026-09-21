"""USASpending — recently posted federal contract & grant awards.
No API key needed. Uses the spending_by_award search endpoint.
"""
from datetime import date, timedelta
import json
import sys

from .http import _session, polite_sleep

CATEGORY = "adjacent"
SOURCE_NAME = "USASpending — new awards"
URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DEFAULT_PRIORITY_AGENCIES = ("Department of Defense",)


def _payload(since, today, limit, agency=None):
    filters = {
        "time_period": [{"start_date": since, "end_date": today}],
        "award_type_codes": ["A", "B", "C", "D"],  # contracts
    }
    if agency:
        filters["agencies"] = [
            {"type": "awarding", "tier": "toptier", "name": agency}
        ]
    return {
        "filters": filters,
        "fields": [
            "Award ID", "Recipient Name", "Awarding Agency", "Start Date",
            "Base Obligation Date", "Last Modified Date", "Award Amount",
            "Description", "generated_internal_id",
        ],
        "sort": "Last Modified Date",
        "order": "desc",
        "limit": limit,
        "page": 1,
    }


def _search(payload, label):
    try:
        resp = _session.post(
            URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(
            f"[detail] USASpending awards ({label}): "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []
    polite_sleep(0.3)
    return resp.json().get("results", [])


def fetch_items(days_back=6, limit=100, priority_agencies=None):
    """Fetch broad recent awards plus targeted agency slices.

    The global newest-awards page is dominated by whichever agency posted a
    batch most recently. Targeted slices ensure high-interest departments do
    not disappear merely because they fell below that global page boundary.
    """
    since = (date.today() - timedelta(days=days_back)).isoformat()
    today = date.today().isoformat()
    priority_agencies = (
        DEFAULT_PRIORITY_AGENCIES
        if priority_agencies is None
        else tuple(priority_agencies)
    )
    results = _search(_payload(since, today, limit), "all agencies")
    for agency in priority_agencies:
        results.extend(
            _search(_payload(since, today, limit, agency=agency), agency)
        )

    items = []
    seen_ids = set()
    for r in results:
        award_id = r.get("Award ID", "")
        recipient = r.get("Recipient Name", "Unknown recipient")
        agency = r.get("Awarding Agency", "")
        start = r.get("Start Date", "")
        # The search window identifies awards changed recently. Treat that
        # modification as the news event; using the original obligation date
        # made current contract changes look years old and retention dropped
        # them before journalists could see them.
        event_date = (
            r.get("Last Modified Date")
            or r.get("Base Obligation Date")
            or start
        )
        amount = r.get("Award Amount", "")
        internal_id = r.get("generated_internal_id", award_id)
        if not internal_id or internal_id in seen_ids:
            continue
        seen_ids.add(internal_id)
        link = f"https://www.usaspending.gov/award/{internal_id}"
        items.append({
            "id": f"usaspending-{internal_id}",
            "title": f"{recipient} — {agency} (${amount})",
            "link": link,
            "summary": r.get("Description") or f"Award {award_id} to {recipient} from {agency}.",
            "published": event_date,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
            "company_name": recipient,
            "entity_name": recipient,
            "department_name": agency,
            "amount": amount,
            "amount_currency": "USD",
            "amount_type": "award_total",
            "event_date": event_date,
        })
    return items
