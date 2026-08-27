"""FEC — recent filings via the OpenFEC API.

Set FEC_API_KEY as a GitHub Actions secret (free, 1,000 req/hr):
https://api.data.gov/signup/
Falls back to DEMO_KEY (very low rate limit) if unset — fine for testing,
not for a real schedule.
"""
import os
import sys
from .http import get

CATEGORY = "fec"
SOURCE_NAME = "FEC — recent filings"
BASE = "https://api.open.fec.gov/v1"


def fetch_items(per_page=40):
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY").strip()
    url = f"{BASE}/filings/"
    params = {
        "api_key": api_key,
        "sort": "-receipt_date",
        "per_page": per_page,
    }
    try:
        resp = get(url, params=params)
    except Exception as exc:
        print(f"[detail] FEC filings: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for f in data.get("results", []):
        filing_id = f.get("file_number") or f.get("filing_id") or f.get("beginning_image_number")
        committee = f.get("committee_name") or f.get("candidate_name") or "Unknown filer"
        form = f.get("form_type", "")
        receipt_date = f.get("receipt_date", "")
        amount = None
        amount_type = None
        for field, label in (
            ("total_contribution_period", "reported_contributions_period"),
            ("total_contributions", "reported_contributions_total"),
            ("total_disbursement_period", "reported_disbursements_period"),
            ("total_disbursements", "reported_disbursements_total"),
        ):
            if f.get(field) is not None:
                amount, amount_type = f[field], label
                break
        pdf = f.get("pdf_url") or f.get("html_url") or f"https://www.fec.gov/data/filings/?data_type=processed&q={filing_id}"
        items.append({
            "id": f"fec-{filing_id}",
            "title": f"{form} — {committee}",
            "link": pdf,
            "summary": f"FEC form {form} filed {receipt_date} by {committee}.",
            "published": receipt_date,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
            "entity_name": committee,
            "department_name": "Federal Election Commission",
            "amount": amount,
            "amount_currency": "USD" if amount is not None else None,
            "amount_type": amount_type,
            "event_date": receipt_date,
        })
    return items
