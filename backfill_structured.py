"""Backfill structured fields from durable raw Neon events."""

from event_store import EventStore


if __name__ == "__main__":
    count = EventStore.from_env().backfill_structured_fields()
    print(f"backfilled {count} event versions")
