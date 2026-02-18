"""Transport rules logic package.

This package provides OpenHIM client integrations, transaction materialization,
persistence, and transport-level rules for telemetry analysis.
"""

from .client import OpenHIMClient
from .ingest import ingest_once, run_ingestion_loop
from .materializer import materialize_transaction
from .models import TransportEvent, TransportRequest, TransportResponse
from .rules import is_failure, is_slow, is_timeout
from .store import TransportEventStore

__all__ = [
    "OpenHIMClient",
    "TransportEvent",
    "TransportRequest",
    "TransportResponse",
    "TransportEventStore",
    "materialize_transaction",
    "is_failure",
    "is_slow",
    "is_timeout",
    "ingest_once",
    "run_ingestion_loop",
]
