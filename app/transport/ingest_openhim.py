from __future__ import annotations

import logging
from typing import Any
import os
import requests

from app.transport.store import TransportEventStore
from app.transport.materializer import materialize_transaction

logger = logging.getLogger(__name__)

# ---------------------------------------
# Exceptions
# ---------------------------------------

class OpenHIMUnavailableError(Exception):
    pass


# ---------------------------------------
# Config
# ---------------------------------------

OPENHIM_BASE_URL = os.getenv("OPENHIM_BASE_URL", "https://openhim-core:8080")
OPENHIM_USERNAME = os.getenv("OPENHIM_USERNAME", "root@openhim.org")
OPENHIM_PASSWORD = os.getenv("OPENHIM_PASSWORD", "Maverick2016!")
OPENHIM_VERIFY_TLS = os.getenv("OPENHIM_VERIFY_TLS", "false").lower() == "true"
OPENHIM_LIMIT = int(os.getenv("OPENHIM_LIMIT", "200"))


# ---------------------------------------
# Helpers
# ---------------------------------------

def _extract_transaction_id(payload: dict) -> str | None:
    """
    OpenHIM uses `_id` as the primary transaction identifier.
    Some custom payloads may use `transactionID`.
    We support both.
    """
    return (
        payload.get("transactionID")
        or payload.get("_id")
    )


def is_openhim_transaction(payload: dict) -> bool:
    return isinstance(payload, dict) and _extract_transaction_id(payload) is not None


def is_fhir_bundle(payload: dict) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("resourceType") == "Bundle"
    )


def openhim_healthcheck() -> bool:
    try:
        response = requests.get(
            f"{OPENHIM_BASE_URL}/heartbeat",
            auth=(OPENHIM_USERNAME, OPENHIM_PASSWORD),
            verify=OPENHIM_VERIFY_TLS,
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


# ---------------------------------------
# Pull Mode
# ---------------------------------------

def ingest_openhim_transactions(
    limit: int | None = None,
    correlation_id: str | None = None,
) -> dict[str, int]:

    limit = limit or OPENHIM_LIMIT

    try:
        response = requests.get(
            f"{OPENHIM_BASE_URL}/transactions?limit={limit}",
            auth=(OPENHIM_USERNAME, OPENHIM_PASSWORD),
            verify=OPENHIM_VERIFY_TLS,
            timeout=10,
        )
    except Exception as exc:
        raise OpenHIMUnavailableError(f"OpenHIM unreachable: {exc}")

    if response.status_code != 200:
        raise OpenHIMUnavailableError(
            f"OpenHIM returned {response.status_code}"
        )

    transactions = response.json()

    # OpenHIM may wrap transactions inside a property depending on version
    if isinstance(transactions, dict):
        transactions = transactions.get("transactions", [])

    processed = 0
    skipped = 0

    for tx in transactions:
        try:
            tx_id, was_skipped = process_openhim_transaction(
                tx,
                correlation_id=correlation_id,
            )
            if was_skipped:
                skipped += 1
            else:
                processed += 1
        except Exception as exc:
            logger.warning(
                "transport_transaction_processing_failed",
                extra={
                    "error": str(exc),
                    "correlation_id": correlation_id,
                },
            )

    return {
        "processed": processed,
        "skipped": skipped,
    }


# ---------------------------------------
# Push Mode Processing
# ---------------------------------------

def process_openhim_transaction(
    payload: dict,
    correlation_id: str | None = None,
) -> tuple[str, bool]:

    transaction_id = _extract_transaction_id(payload)

    if not transaction_id:
        raise ValueError("Missing transactionID or _id")

    store = TransportEventStore()

    # Idempotency check
    if store.transaction_exists(transaction_id):
        logger.info(
            "transport_duplicate_skipped",
            extra={
                "transaction_id": transaction_id,
                "correlation_id": correlation_id,
            },
        )
        return transaction_id, True

    event = materialize_transaction(payload)

    store.upsert_event(event)

    logger.info(
        "transport_transaction_processed",
        extra={
            "transaction_id": transaction_id,
            "correlation_id": correlation_id,
        },
    )

    return transaction_id, False