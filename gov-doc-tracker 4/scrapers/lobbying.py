"""Lobbying disclosures via the LDA.gov REST API.

lda.senate.gov is being retired in favor of lda.gov — this uses the
current host. Register a free key at https://lda.gov/api/register/ and
set it as the LDA_API_KEY GitHub Actions secret. Anonymous access works
too, just rate-limited harder.
"""
import os
import sys
from .http import get

CATEGORY = "lobbying"
SOURCE_NAME = "Lobbying disclosures (LDA.gov)"
BASE = "https://lda.gov/api/v1"


def fetch_items(page_size=40):
    api_key = (os.environ.get("LDA_API_KEY") or "").strip() or None
    headers = {"Authorization": f"Token {api_key}"} if api_key else {}
    url = f"{BASE}/filings/"
    params = {"ordering": "-dt_posted", "page_size": page_size}
    try:
        resp = get(url, params=params, headers=headers)
    except Exception as exc:
        print(f"[detail] Lobbying disclosures: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for f in data.get("results", []):
        client = (f.get("client") or {}).get("name", "Unknown client")
        registrant = (f.get("registrant") or {}).get("name", "Unknown registrant")
        filing_url = f.get("filing_document_url") or f.get("url", "")
        filing_type = f.get("filing_type_display", "Filing")
        posted = f.get("dt_posted", "")
        filing_uuid = f.get("filing_uuid", filing_url)
        items.append({
            "id": f"lda-{filing_uuid}",
            "title": f"{filing_type} — {registrant} for {client}",
            "link": filing_url or "https://lda.gov/",
            "summary": f"{registrant} registered/reported lobbying for {client}.",
            "published": posted,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
        })
    return items
