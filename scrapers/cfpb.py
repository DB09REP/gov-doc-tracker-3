import sys
"""CFPB — recent consumer complaints (public API, no key)."""
from .http import get

CATEGORY = "adjacent"
SOURCE_NAME = "CFPB — recent consumer complaints"
BASE = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"


def fetch_items(size=40):
    params = {"size": size, "sort": "created_date_desc"}
    try:
        resp = get(BASE, params=params)
    except Exception as exc:
        print(f"[detail] CFPB complaints: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for hit in data.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        company = src.get("company", "Unknown company")
        product = src.get("product", "")
        issue = src.get("issue", "")
        date_received = src.get("date_received", "")
        complaint_id = hit.get("_id", "")
        link = f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/detail/{complaint_id}"
        items.append({
            "id": f"cfpb-{complaint_id}",
            "title": f"{company} — {product}",
            "link": link,
            "summary": issue,
            "published": date_received,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
            "company_name": company,
            "entity_name": company,
            "department_name": "Consumer Financial Protection Bureau",
            "event_date": date_received,
        })
    return items
