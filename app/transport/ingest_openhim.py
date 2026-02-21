from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from app.transport.cert_probe import CertInfo, probe_server_cert
from app.transport.client import OpenHIMClient
from app.transport.materializer import materialize_transaction
from app.transport.models import OpenHIMTransactionPayload
from app.transport.store import TransportEventStore

logger = logging.getLogger(__name__)


class OpenHIMUnavailableError(RuntimeError):
    """Raised when OpenHIM cannot be reached in pull/health mode."""


@dataclass(frozen=True)
class OpenHIMSettings:
    base_url: str
    username: str | None
    password: str | None
    verify_tls: bool
    limit: int
    timeout_s: int


def get_openhim_settings() -> OpenHIMSettings:
    base_url = os.getenv("OPENHIM_BASE_URL", "https://localhost:8080").rstrip("/")
    username = os.getenv("OPENHIM_USERNAME", "root@openhim.org")
    password = os.getenv("OPENHIM_PASSWORD", "") or None
    verify_tls = os.getenv("OPENHIM_VERIFY_TLS", "false").lower() in ("1", "true")
    limit = int(os.getenv("OPENHIM_LIMIT", "200"))
    timeout_s = int(os.getenv("OPENHIM_TIMEOUT_SECONDS", "15"))

    return OpenHIMSettings(
        base_url=base_url,
        username=username,
        password=password,
        verify_tls=verify_tls,
        limit=limit,
        timeout_s=timeout_s,
    )


def validate_openhim_config() -> None:
    settings = get_openhim_settings()
    parsed = urlparse(settings.base_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("OPENHIM_BASE_URL must be a valid http(s) URL")

    if settings.limit <= 0:
        raise RuntimeError("OPENHIM_LIMIT must be > 0")

    if settings.timeout_s <= 0:
        raise RuntimeError("OPENHIM_TIMEOUT_SECONDS must be > 0")


def _build_request_url(req: dict[str, Any]) -> str:
    direct_url = req.get("url")
    if isinstance(direct_url, str) and direct_url:
        return direct_url

    host = req.get("host") or ""
    port = req.get("port") or ""
    path = req.get("path") or ""
    querystring = (req.get("querystring") or "").strip()

    qs = ""
    if querystring:
        qs = querystring if querystring.startswith("?") else "?" + querystring

    if host and port:
        base = f"http://{host}:{port}"
    elif host:
        base = f"http://{host}"
    else:
        base = ""

    return f"{base}{path}{qs}"


def _extract_host_port_scheme(request_url: str) -> tuple[str | None, int | None, str | None]:
    try:
        parsed = urlparse(request_url)
        return parsed.hostname, parsed.port, parsed.scheme
    except Exception:
        return None, None, None


def _safe_parse_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _normalize_transaction(raw: dict[str, Any]) -> dict[str, Any]:
    event = materialize_transaction(raw)
    req = raw.get("request") or {}
    response = raw.get("response") or {}
    req_ts_raw = req.get("timestamp") or raw.get("timestamp") or raw.get("created")

    parsed_ts: datetime
    if isinstance(req_ts_raw, str):
        try:
            parsed_ts = datetime.fromisoformat(req_ts_raw.replace("Z", "+00:00"))
            if parsed_ts.tzinfo is None:
                parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
        except ValueError:
            parsed_ts = event.timestamp
    else:
        parsed_ts = event.timestamp

    req_headers = req.get("headers") or event.request.headers
    if not isinstance(req_headers, dict):
        req_headers = {"_raw": str(req_headers)}

    req_url = _build_request_url(req)

    if not req_url:
        req_url = event.request.url

    response_duration = (
        response.get("duration")
        or response.get("duration_ms")
        or raw.get("responseTime")
        or event.response.duration_ms
    )

    return {
        "transaction_id": str(event.transaction_id),
        "channel": str(raw.get("channelID") or raw.get("channel") or event.channel or "UNKNOWN"),
        "request_method": str(req.get("method") or event.request.method or "UNKNOWN").upper(),
        "request_url": str(req_url or ""),
        "request_headers": req_headers,
        "response_status": _safe_parse_int(response.get("status") or response.get("statusCode") or event.response.status),
        "response_duration_ms": _safe_parse_int(response_duration, event.response.duration_ms),
        "source_ip": str(raw.get("clientIP") or req.get("clientIP") or event.source_ip or "") or None,
        "timestamp": parsed_ts,
        "cert_subject_cn": None,
        "cert_subject_san": None,
        "cert_issuer_cn": None,
        "cert_not_before": None,
        "cert_not_after": None,
        "cert_serial": None,
        "cert_sha256": None,
        "cert_status": None,
    }


def _apply_tls_probe(event: dict[str, Any], cert_cache: dict[tuple[str, int], CertInfo]) -> None:
    request_url = event.get("request_url") or ""
    host, port, scheme = _extract_host_port_scheme(request_url)

    if not host or not port or scheme != "https":
        event["cert_status"] = "NOT_HTTPS"
        return

    key = (host, port)
    if key not in cert_cache:
        cert_cache[key] = probe_server_cert(host, port, timeout_sec=3)

    cert = cert_cache[key]
    event["cert_subject_cn"] = cert.subject_cn
    event["cert_subject_san"] = cert.subject_san
    event["cert_issuer_cn"] = cert.issuer_cn
    event["cert_not_before"] = cert.not_before
    event["cert_not_after"] = cert.not_after
    event["cert_serial"] = cert.serial
    event["cert_sha256"] = cert.sha256
    event["cert_status"] = cert.status


def is_openhim_transaction(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    try:
        OpenHIMTransactionPayload.model_validate(payload)
        return True
    except Exception:
        return False


def is_fhir_bundle(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return payload.get("resourceType") == "Bundle"


def build_openhim_client() -> OpenHIMClient:
    settings = get_openhim_settings()
    session = requests.Session()
    session.verify = settings.verify_tls
    return OpenHIMClient(
        base_url=settings.base_url,
        username=settings.username,
        password=settings.password,
        timeout=settings.timeout_s,
        session=session,
    )


def process_openhim_transaction(
    raw_tx: dict[str, Any],
    *,
    store: TransportEventStore | None = None,
    cert_cache: dict[tuple[str, int], CertInfo] | None = None,
    correlation_id: str | None = None,
) -> tuple[str, bool]:
    local_store = store or TransportEventStore()
    cache = cert_cache if cert_cache is not None else {}

    normalized = _normalize_transaction(raw_tx)
    tx_id = normalized["transaction_id"]

    if local_store.transaction_exists(tx_id):
        logger.info(
            "transport_ingest_skip_existing",
            extra={
                "transaction_id": tx_id,
                "channel": normalized.get("channel"),
                "correlation_id": correlation_id,
            },
        )
        return tx_id, True

    _apply_tls_probe(normalized, cache)
    local_store.upsert_event(normalized)

    logger.info(
        "transport_ingest_persisted",
        extra={
            "transaction_id": tx_id,
            "channel": normalized.get("channel"),
            "correlation_id": correlation_id,
        },
    )
    return tx_id, False


def ingest_openhim_transactions(
    *,
    limit: int | None = None,
    correlation_id: str | None = None,
) -> dict[str, int]:
    client = build_openhim_client()
    store = TransportEventStore()
    cert_cache: dict[tuple[str, int], CertInfo] = {}

    try:
        settings = get_openhim_settings()
        transactions = client.get_transactions(limit=limit or settings.limit)
    except requests.RequestException as exc:
        logger.warning(
            "openhim_unreachable",
            extra={"correlation_id": correlation_id, "reason": str(exc)},
        )
        raise OpenHIMUnavailableError("OpenHIM unreachable") from exc

    processed = 0
    skipped = 0

    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        if not is_openhim_transaction(tx):
            logger.warning(
                "transport_ingest_skip_invalid_transaction",
                extra={"correlation_id": correlation_id, "reason": "invalid_structure"},
            )
            continue

        _tx_id, was_skipped = process_openhim_transaction(
            tx,
            store=store,
            cert_cache=cert_cache,
            correlation_id=correlation_id,
        )

        if was_skipped:
            skipped += 1
        else:
            processed += 1

    return {"processed": processed, "skipped": skipped}


def openhim_healthcheck() -> bool:
    client = build_openhim_client()
    try:
        client.get_transactions(limit=1)
        return True
    except (requests.RequestException, ValueError):
        return False
