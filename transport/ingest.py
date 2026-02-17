"""Polling ingestion script for OpenHIM transport events."""

from __future__ import annotations

import logging
import os
import time

from .client import OpenHIMClient
from .materializer import materialize_transaction
from .store import TransportEventStore

logger = logging.getLogger(__name__)


def ingest_once(client: OpenHIMClient, store: TransportEventStore, limit: int = 100) -> int:
    """Fetch, materialize, and persist one batch of transactions."""
    inserted = 0
    for raw_txn in client.get_transactions(limit=limit):
        event = materialize_transaction(raw_txn)
        store.upsert_event(event)
        inserted += 1
    return inserted


def poll_and_ingest(
    client: OpenHIMClient,
    store: TransportEventStore,
    limit: int = 100,
    poll_interval_s: float = 15.0,
) -> None:
    """Continuously poll OpenHIM and persist normalized transport events."""
    logger.info("Starting OpenHIM transport ingestion loop")
    while True:
        try:
            count = ingest_once(client=client, store=store, limit=limit)
            logger.info("Processed %s transport transaction(s)", count)
        except Exception:
            logger.exception("Transport ingest cycle failed")
        time.sleep(poll_interval_s)


def _build_from_env() -> tuple[OpenHIMClient, TransportEventStore, int, float]:
    base_url = os.getenv("OPENHIM_BASE_URL", "http://localhost:8080")
    username = os.getenv("OPENHIM_USERNAME")
    password = os.getenv("OPENHIM_PASSWORD")
    timeout_s = float(os.getenv("OPENHIM_TIMEOUT_S", "10"))

    database_url = os.getenv("TRANSPORT_DATABASE_URL", "sqlite:///transport.db")
    limit = int(os.getenv("OPENHIM_LIMIT", "100"))
    poll_interval_s = float(os.getenv("OPENHIM_POLL_INTERVAL_S", "15"))

    client = OpenHIMClient(
        base_url=base_url,
        username=username,
        password=password,
        timeout_s=timeout_s,
    )
    store = TransportEventStore(database_url=database_url)
    return client, store, limit, poll_interval_s


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    poll_and_ingest(*_build_from_env())
