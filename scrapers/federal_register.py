import sys
"""Federal Register — new rules, proposed rules, notices. No API key needed."""
from datetime import date, timedelta
from .http import get

CATEGORY = "congress"
SOURCE_NAME = "Federal Register — new documents"
BASE = "https://www.federalregister.gov/api/v1/documents.json"


def fetch_items(days_back=2, per_page=40):
    since = (date.today() - timedelta(days=days_back)).isoformat()
    params = {
        "order": "newest",
        "per_page": per_page,
        "conditions[publication_date][gte]": since,
    }
    try:
        resp = get(BASE, params=params)
    except Exception as exc:
        print(f"[detail] Federal Register: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for d in data.get("results", []):
        doc_num = d.get("document_number", "")
        title = d.get("title", "Untitled document")
        link = d.get("html_url", "")
        pub_date = d.get("publication_date", "")
        agencies = ", ".join(a.get("name", "") for a in d.get("agencies", []))
        doc_type = d.get("type", "")
        items.append({
            "id": f"fedreg-{doc_num}",
            "title": f"[{doc_type}] {title}",
            "link": link,
            "summary": f"Agencies: {agencies}" if agencies else "",
            "published": pub_date,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
        })
    return items
