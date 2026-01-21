import json
import re
from typing import Any


_CERT_THUMBPRINT_RE = re.compile(r"thumbprint\"?\s*[:=]\s*\"?([A-Fa-f0-9:]+)")

_TLS_EXPIRED_MARKERS = (
    "cert expired",
    "certificate expired",
    "expired certificate",
)
_TLS_TRUST_MARKERS = (
    "unable to find valid certification path",
    "trust anchor",
    "pkix path building failed",
    "sun.security.validator.validatorexception",
)
_TLS_INVALID_MARKERS = (
    "tls handshake failed",
    "ssl handshake failed",
    "handshake_failure",
    "certificate_unknown",
    "bad_certificate",
)

_HTTP_STATUS_KEYS = ("http_status", "httpStatus", "status_code", "statusCode")


def _coerce_http_status(payload: Any) -> int | None:
    if isinstance(payload, dict):
        for key in _HTTP_STATUS_KEYS:
            value = payload.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return None


def _extract_thumbprint(text: str) -> str | None:
    match = _CERT_THUMBPRINT_RE.search(text)
    if not match:
        return None
    return match.group(1)


def extract_transport_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Inspects telemetry events and returns certificate-related evidence.
    Returns only fields that can be proven from data.
    """
    evidence = {
        "cert_status": None,
        "cert_thumbprint": None,
        "failure_stage": None,
        "root_cause": None,
        "http_status": None,
    }

    has_transport_event = any(
        event.get("event_layer") == "TRANSPORT" for event in events
    )
    tls_error_detected = False

    for event in events:
        if event.get("event_layer") != "TRANSPORT":
            continue

        raw_payload = event.get("raw_payload") or ""
        payload_text = raw_payload.lower()
        parsed_payload = None

        if isinstance(raw_payload, str):
            try:
                parsed_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                parsed_payload = None

        thumbprint = _extract_thumbprint(raw_payload)
        if thumbprint:
            evidence["cert_thumbprint"] = thumbprint

        http_status = _coerce_http_status(parsed_payload)
        if http_status is not None:
            evidence["http_status"] = http_status

        if any(marker in payload_text for marker in _TLS_EXPIRED_MARKERS):
            tls_error_detected = True
            evidence.update(
                {
                    "cert_status": "EXPIRED",
                    "failure_stage": "TLS_HANDSHAKE",
                    "root_cause": "CERT_EXPIRED",
                }
            )
            continue

        if any(marker in payload_text for marker in _TLS_TRUST_MARKERS):
            tls_error_detected = True
            evidence.update(
                {
                    "cert_status": "UNTRUSTED",
                    "failure_stage": "TLS_HANDSHAKE",
                    "root_cause": "TRUST_ANCHOR",
                }
            )
            continue

        if any(marker in payload_text for marker in _TLS_INVALID_MARKERS):
            tls_error_detected = True
            evidence.update(
                {
                    "cert_status": "INVALID",
                    "failure_stage": "TLS_HANDSHAKE",
                    "root_cause": "CERT_INVALID",
                }
            )

        status = event.get("status")
        if status == "TIMEOUT":
            evidence["failure_stage"] = evidence["failure_stage"] or "TRANSPORT"
            evidence["root_cause"] = evidence["root_cause"] or "TIMEOUT"
            evidence["http_status"] = evidence["http_status"] or 504

    if has_transport_event and not tls_error_detected:
        evidence["cert_status"] = evidence["cert_status"] or "VALID"

    if any(value is not None for value in evidence.values()):
        return evidence

    return {
        "cert_status": None,
        "cert_thumbprint": None,
        "failure_stage": None,
        "root_cause": None,
        "http_status": None,
    }
