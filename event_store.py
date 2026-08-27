"""Durable event storage backed by Neon Postgres."""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from dates import parse_date
from normalization import enrich_item
from retention import (
    classify_event_date,
    retained_parameters,
    retained_sql,
    retention_window,
)


@dataclass(frozen=True)
class IngestionResult:
    received: int
    accepted: int
    rejected_expired: int
    rejected_future: int


def load_local_env():
    """Load developer credentials without overriding injected CI secrets."""
    root = Path(__file__).parent
    load_dotenv(root / ".env.local", override=False)
    load_dotenv(root / ".env", override=False)


class EventStore:
    def __init__(self, database_url):
        self.database_url = database_url

    @classmethod
    def from_env(cls):
        load_local_env()
        database_url = (os.environ.get("DATABASE_URL") or "").strip()
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required. Run `neon env pull` locally or set "
                "the DATABASE_URL GitHub Actions secret."
            )
        return cls(database_url)

    @staticmethod
    def _normalized_payload(item):
        return json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)

    def store_items(self, items, *, observed_at=None):
        """Store retained events and report records rejected by date policy."""
        observed_at = observed_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        items = list(items)
        rows = []
        rejected_expired = 0
        rejected_future = 0
        for raw_item in items:
            # Version identity reflects source facts, not later changes to the
            # derived normalization rules.
            payload = self._normalized_payload(raw_item)
            item = enrich_item(raw_item)
            external_id = str(item.get("id") or "").strip()
            if not external_id:
                raise ValueError("Scraper item is missing a stable id")

            retention_status = classify_event_date(item.get("event_date"), observed_at)
            if retention_status == "expired":
                rejected_expired += 1
                continue
            if retention_status == "future":
                rejected_future += 1
                continue

            published_at = parse_date(item.get("published")) or observed_at
            rows.append(
                (
                    str(item.get("source_name") or "Unknown source"),
                    external_id,
                    str(item.get("category") or "uncategorized"),
                    str(item.get("title") or "Untitled"),
                    str(item.get("link") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("published") or ""),
                    published_at,
                    hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    payload,
                    observed_at,
                    item.get("company_name"),
                    item.get("entity_name"),
                    item.get("department_name"),
                    item.get("amount"),
                    item.get("amount_currency"),
                    item.get("amount_type"),
                    item.get("event_date"),
                )
            )

        if rows:
            statement = """
            INSERT INTO gov_doc_events (
                source_name, external_id, category, title, link, summary,
                raw_published, published_at, payload_hash, raw_payload,
                last_seen_at, company_name, entity_name, department_name,
                amount_value, amount_currency, amount_type, event_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                    %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_name, external_id, payload_hash)
            DO UPDATE SET
                last_seen_at = EXCLUDED.last_seen_at,
                company_name = EXCLUDED.company_name,
                entity_name = EXCLUDED.entity_name,
                department_name = EXCLUDED.department_name,
                amount_value = EXCLUDED.amount_value,
                amount_currency = EXCLUDED.amount_currency,
                amount_type = EXCLUDED.amount_type,
                event_date = EXCLUDED.event_date
            """
            with psycopg.connect(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.executemany(statement, rows)
        return IngestionResult(
            received=len(items),
            accepted=len(rows),
            rejected_expired=rejected_expired,
            rejected_future=rejected_future,
        )

    def prune_expired(self, *, as_of=None):
        """Physically delete dated and undated rows outside retention."""
        window = retention_window(as_of)
        statement = """
            DELETE FROM gov_doc_events
             WHERE (event_date IS NOT NULL AND (event_date < %s OR event_date > %s))
                OR (event_date IS NULL AND
                    (first_seen_at < %s OR first_seen_at >= %s))
        """
        with psycopg.connect(self.database_url) as connection:
            result = connection.execute(
                statement,
                (
                    window.cutoff,
                    window.today,
                    window.first_seen_start,
                    window.first_seen_end,
                ),
            )
        return result.rowcount

    def fetch_items(self, *, category=None, limit=500):
        """Return recent immutable event versions for feed generation."""
        retention = retained_sql()
        parameters = list(retained_parameters())
        if category is None:
            statement = f"""
                SELECT source_name, external_id, category, title, link, summary,
                       published_at, payload_hash, company_name, entity_name,
                       department_name, amount_value, amount_currency,
                       amount_type, event_date
                  FROM gov_doc_events
                 WHERE {retention}
                 ORDER BY published_at DESC, first_seen_at DESC
                 LIMIT %s
            """
            parameters.append(limit)
        else:
            statement = f"""
                SELECT source_name, external_id, category, title, link, summary,
                       published_at, payload_hash, company_name, entity_name,
                       department_name, amount_value, amount_currency,
                       amount_type, event_date
                  FROM gov_doc_events
                 WHERE {retention} AND category = %s
                 ORDER BY published_at DESC, first_seen_at DESC
                 LIMIT %s
            """
            parameters.extend((category, limit))
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, tuple(parameters))
                rows = cursor.fetchall()

        return [
            {
                "id": f"{row['external_id']}:{row['payload_hash'][:16]}",
                "title": row["title"],
                "link": row["link"],
                "summary": row["summary"],
                "published": row["published_at"],
                "category": row["category"],
                "source_name": row["source_name"],
                "company_name": row["company_name"],
                "entity_name": row["entity_name"],
                "department_name": row["department_name"],
                "amount": row["amount_value"],
                "amount_currency": row["amount_currency"],
                "amount_type": row["amount_type"],
                "event_date": row["event_date"],
            }
            for row in rows
        ]

    def backfill_structured_fields(self):
        """Populate query fields on events stored before migration 002."""
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                "SELECT id, raw_payload FROM gov_doc_events"
            ).fetchall()
            updates = []
            for row in rows:
                item = enrich_item(row["raw_payload"])
                updates.append(
                    (
                        item.get("company_name"), item.get("entity_name"),
                        item.get("department_name"), item.get("amount"),
                        item.get("amount_currency"), item.get("amount_type"),
                        item.get("event_date"), row["id"],
                    )
                )
            connection.cursor().executemany(
                """
                UPDATE gov_doc_events
                   SET company_name = %s, entity_name = %s,
                       department_name = %s, amount_value = %s,
                       amount_currency = %s, amount_type = %s, event_date = %s
                 WHERE id = %s
                """,
                updates,
            )
        return len(updates)

    def search_events(self, filters):
        """Search the newest version of each source event for the dashboard."""
        retention = retained_sql()
        retention_params = list(retained_parameters())
        conditions = []
        parameters = []
        mappings = {
            "company": ("company_name = %s", str),
            "department": ("department_name = %s", str),
            "source": ("source_name = %s", str),
            "min_amount": ("amount_value >= %s", str),
            "max_amount": ("amount_value <= %s", str),
            "date_from": ("event_date >= %s", str),
            "date_to": ("event_date <= %s", str),
        }
        for name, (condition, convert) in mappings.items():
            value = filters.get(name)
            if value not in (None, ""):
                conditions.append(condition)
                parameters.append(convert(value))
        if filters.get("has_amount") in (True, "true", "1"):
            conditions.append("amount_value IS NOT NULL")
        if filters.get("q"):
            conditions.append(
                "(title ILIKE %s OR summary ILIKE %s OR company_name ILIKE %s "
                "OR entity_name ILIKE %s OR department_name ILIKE %s)"
            )
            parameters.extend([f"%{filters['q']}%"] * 5)

        orderings = {
            "newest": "event_date DESC NULLS LAST, first_seen_at DESC",
            "oldest": "event_date ASC NULLS LAST, first_seen_at DESC",
            "amount_desc": "amount_value DESC NULLS LAST, event_date DESC NULLS LAST",
            "amount_asc": "amount_value ASC NULLS LAST, event_date DESC NULLS LAST",
        }
        ordering = orderings.get(filters.get("sort"), orderings["newest"])
        try:
            limit = min(max(int(filters.get("limit", 100)), 1), 500)
        except (TypeError, ValueError):
            limit = 100
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        statement = f"""
            WITH latest AS (
                SELECT DISTINCT ON (source_name, external_id)
                       id, source_name, external_id, category, title, link,
                       summary, company_name, entity_name, department_name,
                       amount_value, amount_currency, amount_type, event_date,
                       published_at, first_seen_at, last_seen_at
                FROM gov_doc_events
                WHERE {retention}
                 ORDER BY source_name, external_id, first_seen_at DESC
            ), scored AS (
                SELECT latest.*,
                       CASE WHEN amount_value IS NOT NULL THEN
                           PERCENT_RANK() OVER (
                               PARTITION BY source_name, amount_type
                               ORDER BY amount_value
                           )
                       END AS amount_percentile
                  FROM latest
            )
            SELECT * FROM scored
            {where}
            ORDER BY {ordering}
            LIMIT %s
        """
        parameters = retention_params + parameters + [limit]
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(statement, parameters).fetchall()
            facets = connection.execute(
                f"""
                WITH latest AS (
                    SELECT DISTINCT ON (source_name, external_id)
                           source_name, company_name, department_name
                      FROM gov_doc_events
                     WHERE {retention}
                     ORDER BY source_name, external_id, first_seen_at DESC
                )
                SELECT
                    ARRAY(SELECT DISTINCT source_name FROM latest ORDER BY source_name) AS sources,
                    ARRAY(
                        SELECT company_name
                          FROM latest
                         WHERE company_name IS NOT NULL
                         GROUP BY company_name
                         ORDER BY COUNT(*) DESC, company_name
                         LIMIT 500
                    ) AS companies,
                    ARRAY(SELECT DISTINCT department_name FROM latest WHERE department_name IS NOT NULL ORDER BY department_name) AS departments
                """,
                tuple(retention_params),
            ).fetchone()
        return rows, facets

    def verify(self):
        """Verify end-to-end application connectivity without using the CLI."""
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone()[0] == 1
