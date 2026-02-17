"""Transport-level rule helpers."""

from .models import TransportEvent


def is_failure(event: TransportEvent) -> bool:
    """Return True when transaction response indicates a server failure."""
    return event.response.status >= 500


def is_slow(event: TransportEvent, threshold_ms: int = 500) -> bool:
    """Return True when response duration exceeds the threshold."""
    return event.response.duration_ms > threshold_ms


def is_timeout(event: TransportEvent, threshold_ms: int = 30000) -> bool:
    """Return True for HTTP timeout status or excessive duration."""
    return event.response.status == 408 or event.response.duration_ms > threshold_ms
