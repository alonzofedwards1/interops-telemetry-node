import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import requests

from app.transport.store import TransportEventStore
from app.transport.cert_probe import probe_server_cert

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------

class OpenHIMUnavailableError(Exception):
    """Raised when OpenHIM cannot be reached in pull mode."""
    pass


# ---------------------------------------------------------
# Config Validation
# ---------------------------------------------------------

def validate_openhim_config() -> None:
    base_url = os.getenv("OPENHIM_BASE_URL")
    if not base_url:
        raise RuntimeError("OPENHIM_BASE_URL is required")

    if not base_url.startswith("http"):
        raise RuntimeError("OPENHIM_BASE_URL must start with http/https")

    logger.info("OpenHIM configuration validated.")


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _should_probe_cert(host: Optional[str], port: Optional[int]) -> bool:
    if not host or not port:
        return False
    return port in (443, 8443)


def _fetch_transactions_from_openhim() -> List[Dict[str, Any]]:
    base_url = os.getenv("OPENHIM_BASE_URL", "https://openhim-core:8080").rstrip("/")
    username = os.getenv("OPENHIM_USERNAME", "root@openhim.org")
    password = os.getenv("OPENHIM_PASSWORD", "")
    verify_tls = os.getenv("OPENHIM_VERIFY_TLS", "false").lower() in ("1", "true")
    limit = int(os.getenv("OPENHIM_LIMIT", "200"))

    url = f"{base_url}/transactions?limit={limit}"

    try:
        response = requests.get(
            url,
            auth=(username, password) if password else None,
            verify=verify_tls,
            timeout=15,
        )
    except requests.RequestException as e:
        raise OpenHIMUnavailableError(str(e))

    if response.status_code != 200:
        raise OpenHIMUnavailableError(
            f"OpenHIM responded {response.status_code}"
        )

    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected OpenHIM transaction payload format")

    return data


# ---------------------------------------------------------
# Main Ingest Function
# ---------------------------------------------------------

def ingest_openhim_transactions(
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> None:
    """
    Supports:
    - Push mode (payload provided by OpenHIM)
    - Pull mode (no payload; fetch from OpenHIM)

    Writes ONLY to transport_events.
    """

    store = TransportEventStore()
    cert_cache: Dict[tuple, Any] = {}

    # -----------------------------------------------------
    # Determine Mode
    # -----------------------------------------------------

    if payload:
        logger.info("Push mode ingestion triggered.")
        transactions = [payload]
    else:
        logger.info("Pull mode ingestion triggered.")
        transactions = _fetch_transactions_from_openhim()

    # -----------------------------------------------------
    # Process Transactions
    # -----------------------------------------------------

    for tx in transactions:
        try:
            tx_id = str(tx.get("_id") or tx.get("id") or "")
            if not tx_id:
                logger.warning("Skipping transaction with no ID.")
                continue

            # Idempotency guard
            if store.transaction_exists(tx_id):
                logger.info("Skipping duplicate transaction %s", tx_id)
                continue

            request_data = tx.get("request", {})
            response_data = tx.get("response", {})

            request_method = (request_data.get("method") or "UNKNOWN").upper()
            request_url = request_data.get("path") or ""
            headers_data = request_data.get("headers") or {}
            response_status = int(response_data.get("status") or 0)

            # Timestamp handling
            timestamp_str = request_data.get("timestamp")
            timestamp = (
                datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if timestamp_str
                else _utc_now()
            )

            # TLS Probe (safe, HTTPS only)
            host = request_data.get("host")
            port = request_data.get("port")

            cert = None
            if _should_probe_cert(host, port):
                key = (host, port)
                if key not in cert_cache:
                    try:
                        cert_cache[key] = probe_server_cert(host, port)
                    except Exception:
                        cert_cache[key] = None
                cert = cert_cache[key]

            event = {
                "transaction_id": tx_id,
                "channel": tx.get("channelID") or "UNKNOWN",
                "request_method": request_method,
                "request_url": request_url,
                "request_headers": headers_data,
                "response_status": response_status,
                "response_duration_ms": int(response_data.get("duration") or 0),
                "source_ip": tx.get("clientIP"),
                "timestamp": timestamp,
                "cert_subject_cn": getattr(cert, "subject_cn", None) if cert else None,
                "cert_subject_san": getattr(cert, "subject_san", None) if cert else None,
                "cert_issuer_cn": getattr(cert, "issuer_cn", None) if cert else None,
                "cert_not_before": getattr(cert, "not_before", None) if cert else None,
                "cert_not_after": getattr(cert, "not_after", None) if cert else None,
                "cert_serial": getattr(cert, "serial", None) if cert else None,
                "cert_sha256": getattr(cert, "sha256", None) if cert else None,
                "cert_status": getattr(cert, "status", None) if cert else None,
            }

            store.upsert_event(event)

        except Exception as e:
            logger.error(
                "Failed processing transaction %s: %s",
                tx.get("_id"),
                str(e),
                exc_info=True,
            )

    logger.info("Transport ingestion complete.")