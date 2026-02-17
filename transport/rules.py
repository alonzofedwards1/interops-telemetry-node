"""Transport-level rules for event quality and reliability checks."""

from __future__ import annotations

from .models import TransportEvent


def is_failure(event: TransportEvent) -> bool:
    """Return ``True`` when the response status indicates server failure."""

    return event.response.status >= 500


def is_slow(event: TransportEvent, threshold_ms: int = 500) -> bool:
    """Return ``True`` when transaction latency exceeds ``threshold_ms``."""

    return event.response.duration_ms > threshold_ms


def is_timeout(event: TransportEvent, timeout_threshold_ms: int = 30_000) -> bool:
    """Return ``True`` when response is a timeout or exceeds timeout threshold."""

    return (
        event.response.status == 408
        or event.response.duration_ms > timeout_threshold_ms
    )
