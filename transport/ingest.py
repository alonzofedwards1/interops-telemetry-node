"""Ingestion workflow for polling OpenHIM and storing normalized events."""

from __future__ import annotations

import logging
import os
import time

from .client import OpenHIMClient
from .materializer import materialize_transaction
from .store import TransportEventStore

logger = logging.getLogger(__name__)


DEFAULT_TRANSPORT_DB_URL = "postgresql://interoplens:devpassword@localhost:5432/interoplens"


def ingest_once(client: OpenHIMClient, store: TransportEventStore, limit: int = 100) -> int:
    """Fetch and persist up to ``limit`` transactions from OpenHIM.

    Returns:
        Number of events upserted in the local database.
    """

    raw_transactions = client.get_transactions(limit=limit)
    count = 0

    for raw in raw_transactions:
        event = materialize_transaction(raw)
        if event.transaction_id == "unknown":
            logger.warning("Skipping transaction with missing ID", extra={"raw": raw})
            continue
        store.upsert_event(event)
        count += 1

    return count


def run_ingestion_loop(
    client: OpenHIMClient,
    store: TransportEventStore,
    poll_interval_seconds: int = 30,
    limit: int = 100,
) -> None:
    """Run an endless polling loop that ingests transactions into the DB."""

    logger.info("Starting transport ingestion loop")

    while True:
        try:
            inserted = ingest_once(client=client, store=store, limit=limit)
            logger.info("Ingested %s transaction(s)", inserted)
        except Exception:  # noqa: BLE001
            logger.exception("Transport ingestion cycle failed")

        time.sleep(poll_interval_seconds)


def main() -> None:
    """CLI entrypoint for transport ingestion."""

    logging.basicConfig(level=logging.INFO)

    base_url = os.getenv("OPENHIM_BASE_URL", "http://localhost:8080")
    username = os.getenv("OPENHIM_USERNAME")
    password = os.getenv("OPENHIM_PASSWORD")
    timeout = int(os.getenv("OPENHIM_TIMEOUT", "10"))

    db_url = os.getenv("TRANSPORT_DB_URL", os.getenv("DATABASE_URL", DEFAULT_TRANSPORT_DB_URL))
    limit = int(os.getenv("OPENHIM_LIMIT", "100"))
    poll_interval = int(os.getenv("OPENHIM_POLL_INTERVAL", "30"))

    client = OpenHIMClient(
        base_url=base_url,
        username=username,
        password=password,
        timeout=timeout,
    )
    store = TransportEventStore(database_url=db_url)
    store.create_tables()

    run_ingestion_loop(
        client=client,
        store=store,
        poll_interval_seconds=poll_interval,
        limit=limit,
    )


if __name__ == "__main__":
    main()
