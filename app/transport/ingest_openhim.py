from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests

from app.transport.certificate_provider import (
    CertificateProvider,
    CertificateProviderError,
    OpenHIMApiCertificateProvider,
)
from app.transport.materializer import materialize_transaction
from app.transport.models import TransportEvent
from app.transport.store import EndpointInput, TransportEventStore

logger = logging.getLogger(__name__)


class OpenHIMUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class OpenHIMTransportConfig:
    api_base_url: str
    api_username: str
    api_password: str
    api_verify_tls: bool
    tls_host: str
    tls_port: int


TRANSPORT_CONFIG = OpenHIMTransportConfig(
    api_base_url=os.getenv("OPENHIM_API_BASE_URL", os.getenv("OPENHIM_BASE_URL", "https://openhim-core:8080")),
    api_username=os.getenv("OPENHIM_API_USERNAME", os.getenv("OPENHIM_USERNAME", "root@openhim.org")),
    api_password=os.getenv("OPENHIM_API_PASSWORD", os.getenv("OPENHIM_PASSWORD", "")),
    api_verify_tls=os.getenv("OPENHIM_API_VERIFY_TLS", os.getenv("OPENHIM_VERIFY_TLS", "false")).lower() == "true",
    tls_host=os.getenv("OPENHIM_TLS_HOST", "localhost"),
    tls_port=int(os.getenv("OPENHIM_TLS_PORT", "5001")),
)
OPENHIM_LIMIT = int(os.getenv("OPENHIM_LIMIT", "200"))
OPENHIM_MAX_PAGES = int(os.getenv("OPENHIM_MAX_PAGES", "20"))


def _extract_transaction_id(payload: dict) -> str | None:
    return payload.get("transactionID") or payload.get("_id") or payload.get("id")


def _extract_transactions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("transactions", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def is_openhim_transaction(payload: dict) -> bool:
    return isinstance(payload, dict) and _extract_transaction_id(payload) is not None


def is_fhir_bundle(payload: dict) -> bool:
    return isinstance(payload, dict) and payload.get("resourceType") == "Bundle"


def _build_certificate_provider() -> CertificateProvider:
    return OpenHIMApiCertificateProvider(
        base_url=TRANSPORT_CONFIG.api_base_url,
        username=TRANSPORT_CONFIG.api_username,
        password=TRANSPORT_CONFIG.api_password,
        verify_tls=TRANSPORT_CONFIG.api_verify_tls,
    )


def openhim_healthcheck() -> bool:
    try:
        response = requests.get(
            f"{TRANSPORT_CONFIG.api_base_url}/heartbeat",
            auth=(TRANSPORT_CONFIG.api_username, TRANSPORT_CONFIG.api_password),
            verify=TRANSPORT_CONFIG.api_verify_tls,
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


def ingest_openhim_transactions(
        limit: int | None = None,
        correlation_id: str | None = None,
) -> dict[str, int]:
    limit = limit or OPENHIM_LIMIT

    transactions: list[dict[str, Any]] = []
    seen_transaction_ids: set[str] = set()
    skip = 0

    for page_number in range(OPENHIM_MAX_PAGES):
        try:
            response = requests.get(
                f"{TRANSPORT_CONFIG.api_base_url}/transactions",
                params={"limit": limit, "skip": skip},
                auth=(TRANSPORT_CONFIG.api_username, TRANSPORT_CONFIG.api_password),
                verify=TRANSPORT_CONFIG.api_verify_tls,
                timeout=10,
            )
        except Exception as exc:
            raise OpenHIMUnavailableError(f"OpenHIM unreachable: {exc}")

        if response.status_code != 200:
            raise OpenHIMUnavailableError(f"OpenHIM returned {response.status_code}")

        page_transactions = _extract_transactions(response.json())

        if not page_transactions:
            break

        added = 0
        for tx in page_transactions:
            tx_id = _extract_transaction_id(tx)
            if tx_id and tx_id in seen_transaction_ids:
                continue

            transactions.append(tx)
            if tx_id:
                seen_transaction_ids.add(tx_id)
            added += 1

        logger.info(
            "transport_transactions_page_pulled",
            extra={
                "page_number": page_number,
                "page_skip": skip,
                "page_count": len(page_transactions),
                "added_count": added,
                "correlation_id": correlation_id,
            },
        )

        if len(page_transactions) < limit:
            break

        skip += limit

    logger.info(
        "transport_transactions_pulled",
        extra={
            "transaction_count": len(transactions),
            "correlation_id": correlation_id,
        },
    )

    processed = 0
    skipped = 0

    for tx in transactions:
        tx_id = _extract_transaction_id(tx) if isinstance(tx, dict) else None
        logger.info(
            "transport_transaction_processing_started",
            extra={
                "transaction_id": tx_id or "unknown",
                "channelID": tx.get("channelID") if isinstance(tx, dict) else None,
                "correlation_id": correlation_id,
            },
        )
        try:
            tx_id_result, was_skipped = process_openhim_transaction(
                tx,
                correlation_id=correlation_id,
            )

            if was_skipped:
                skipped += 1
            else:
                processed += 1
            tx_id = tx_id_result
        except Exception as exc:
            skipped += 1
            logger.exception(
                "transport_transaction_processing_failed",
                extra={
                    "transaction_id": tx_id or "unknown",
                    "channelID": tx.get("channelID") if isinstance(tx, dict) else None,
                    "correlation_id": correlation_id,
                    "error": str(exc),
                },
            )

    return {"processed": processed, "skipped": skipped}


def process_openhim_transaction(
    payload: dict,
    correlation_id: str | None = None,
    cert_provider: CertificateProvider | None = None,
) -> tuple[str, bool]:

    transaction_id = _extract_transaction_id(payload) or "unknown"

    store = TransportEventStore()

    if store.transaction_exists(transaction_id):
        logger.info(
            "transport_duplicate_skipped",
            extra={
                "transaction_id": transaction_id,
                "channelID": payload.get("channelID") or payload.get("channel"),
                "correlation_id": correlation_id,
            },
        )
        return transaction_id, True

    event = materialize_transaction(payload)

    if event is None:
        logger.warning(
            "transport_transaction_materialization_failed",
            extra={
                "transaction_id": transaction_id,
                "channelID": payload.get("channelID") or payload.get("channel"),
                "correlation_id": correlation_id,
            },
        )
        return transaction_id or "unknown", True

    endpoint_id = store.upsert_endpoint(
        EndpointInput(
            name="openhim-core",
            host=TRANSPORT_CONFIG.tls_host,
            port=TRANSPORT_CONFIG.tls_port,
            scheme="https",
            service_type="openhim",
        )
    )

    cert_id: int | None = None
    active_provider = cert_provider or _build_certificate_provider()

    try:
        cert_payload = active_provider.get_server_cert()
        cert_id = store.upsert_certificate(cert_payload)
        store.insert_endpoint_cert_observation(
            endpoint_id=endpoint_id,
            cert_id=cert_id,
            source=cert_payload.source,
        )
    except CertificateProviderError as exc:
        logger.warning(
            "transport_certificate_fetch_failed",
            extra={
                "transaction_id": transaction_id,
                "channelID": payload.get("channelID") or payload.get("channel"),
                "correlation_id": correlation_id,
                "error": str(exc),
            },
        )

    event_row = _to_transport_row(event, endpoint_id=endpoint_id, cert_id=cert_id)
    store.upsert_event(event_row)

    logger.info(
        "transport_transaction_processed",
        extra={
            "transaction_id": transaction_id,
            "channelID": payload.get("channelID") or payload.get("channel"),
            "correlation_id": correlation_id,
        },
    )

    return transaction_id, False


def _to_transport_row(event: TransportEvent, endpoint_id: int, cert_id: int | None) -> dict[str, Any]:
    return {
        "transaction_id": event.transaction_id,
        "channel": event.channel,
        "request_method": event.request.method,
        "request_url": event.request.url,
        "request_headers": event.request.headers,
        "response_status": event.response.status,
        "response_duration_ms": event.response.duration_ms,
        "source_ip": event.source_ip,
        "timestamp": event.timestamp,
        "endpoint_id": endpoint_id,
        "cert_id": cert_id,
        "cert_status": "VALID" if cert_id is not None else None,
        "cert_subject_cn": None,
        "cert_subject_san": None,
        "cert_issuer_cn": None,
        "cert_not_before": None,
        "cert_not_after": None,
        "cert_serial": None,
        "cert_sha256": None,
    }
