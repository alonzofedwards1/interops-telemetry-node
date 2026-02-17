from __future__ import annotations

from .models import TransportEvent


def is_failure(event: TransportEvent) -> bool:

    return event.response.status >= 500


def is_slow(event: TransportEvent, threshold_ms: int = 500) -> bool:

    return event.response.duration_ms > threshold_ms


def is_timeout(event: TransportEvent, timeout_threshold_ms: int = 30_000) -> bool:

    return (
        event.response.status == 408
        or event.response.duration_ms > timeout_threshold_ms
    )
