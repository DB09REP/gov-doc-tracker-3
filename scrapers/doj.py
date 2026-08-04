"""DOJ press releases (national + U.S. Attorneys' Offices) via the
documented justice.gov JSON API.
Docs: https://www.justice.gov/developer/api-documentation/api_v1
"""
import sys
from .http import get

CATEGORY = "courts"
SOURCE_NAME = "DOJ press releases"
BASE = "https://www.justice.gov/api/v1/press_releases.json"


def fetch_items(page_size=40):
    params = {"pagesize": page_size}
    try:
        resp = get(BASE, params=params)
    except Exception as exc:
        print(f"[detail] DOJ press releases: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for r in data.get("results", []):
        title = r.get("title", "Untitled release")
        link = r.get("url") or r.get("field_pr_url") or ""
        date = r.get("date") or r.get("created", "")
        body = (r.get("body") or "")[:300]
        raw_component = r.get("component", "")
        if isinstance(raw_component, list):
            names = []
            for c in raw_component:
                if isinstance(c, dict):
                    names.append(c.get("name") or c.get("title") or str(c.get("id", "")))
                else:
                    names.append(str(c))
            component = ", ".join(n for n in names if n)
        else:
            component = str(raw_component or "")
        nid = r.get("nid", link)
        items.append({
            "id": f"doj-{nid}",
            "title": title,
            "link": link if link.startswith("http") else f"https://www.justice.gov{link}",
            "summary": f"{component + ': ' if component else ''}{body}",
            "published": date,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
        })
    return items
