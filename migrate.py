"""Apply unapplied SQL migrations to Neon using the direct connection."""

import os
from pathlib import Path

import psycopg

from event_store import load_local_env

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def main():
    load_local_env()
    database_url = (
        os.environ.get("DATABASE_URL_UNPOOLED")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL_UNPOOLED is required for migrations")

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gov_doc_schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            applied = connection.execute(
                "SELECT 1 FROM gov_doc_schema_migrations WHERE filename = %s",
                (path.name,),
            ).fetchone()
            if applied:
                print(f"migration already applied: {path.name}")
                continue

            connection.execute(path.read_text(), prepare=False)
            connection.execute(
                "INSERT INTO gov_doc_schema_migrations (filename) VALUES (%s)",
                (path.name,),
            )
            print(f"migration applied: {path.name}")


if __name__ == "__main__":
    main()
