import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from app.db.connection import get_connection
from app.transport.store import upsert_transport_event

logger = logging.getLogger(__name__)


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _build_request_url(req: Dict[str, Any]) -> str:
    host = req.get("host") or ""
    port = req.get("port") or ""
    path = req.get("path") or ""
    querystring = req.get("querystring") or ""

    qs = querystring.strip()
    if qs and not qs.startswith("?"):
        qs = "?" + qs

    base = f"http://{host}:{port}" if host and port else f"http://{host}" if host else ""
    return f"{base}{path}{qs}"


def _calc_duration_ms(req_ts: Optional[datetime], resp_ts: Optional[datetime]) -> int:
    if not req_ts or not resp_ts:
        return 0
    delta = resp_ts - req_ts
    return max(int(delta.total_seconds() * 1000), 0)


def ingest_openhim_transactions() -> None:
    base_url = os.getenv("OPENHIM_BASE_URL", "https://localhost:8080").rstrip("/")
    username = os.getenv("OPENHIM_USERNAME", "root@openhim.org")
    password = os.getenv("OPENHIM_PASSWORD", "Maverick2016!")
    verify_tls = os.getenv("OPENHIM_VERIFY_TLS", "false").lower() in ("1", "true")
    limit = int(os.getenv("OPENHIM_LIMIT", "200"))

    url = f"{base_url}/transactions"
    params = {"limit": limit}
    full_url = url + "?" + urlencode(params)

    logger.info("Fetching OpenHIM transactions from %s", full_url)

    response = requests.get(
        full_url,
        auth=(username, password),
        verify=verify_tls,
        timeout=30,
        headers={"Accept": "application/json"},
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenHIM /transactions failed: {response.status_code} {response.text[:300]}"
        )

    transactions = response.json()

    if not isinstance(transactions, list):
        raise RuntimeError("Expected list from OpenHIM /transactions")

    conn = get_connection()

    try:
        for tx in transactions:
            try:
                tx_id = tx.get("_id")
                if not tx_id:
                    continue

                channel = tx.get("channelID") or "UNKNOWN"
                source_ip = tx.get("clientIP")

                req = tx.get("request") or {}
                res = tx.get("response") or {}

                req_method = (req.get("method") or "UNKNOWN").upper()
                req_url = _build_request_url(req)

                headers = req.get("headers") or {}
                if not isinstance(headers, dict):
                    headers = {"_raw": str(headers)}

                req_ts = _parse_ts(req.get("timestamp"))
                res_ts = _parse_ts(res.get("timestamp"))

                duration_ms = _calc_duration_ms(req_ts, res_ts)
                status = int(res.get("status") or 0)

                upsert_transport_event(
                    conn=conn,
                    transaction_id=str(tx_id),
                    channel=str(channel),
                    request_method=req_method,
                    request_url=req_url,
                    request_headers=headers,
                    response_status=status,
                    response_duration_ms=duration_ms,
                    source_ip=str(source_ip) if source_ip else None,
                    timestamp=req_ts or datetime.now(timezone.utc),
                )

            except Exception as e:
                logger.error("Failed processing transaction: %s", e)

        conn.commit()
        logger.info("OpenHIM ingest complete.")

    finally:
        conn.close()
