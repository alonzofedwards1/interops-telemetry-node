"""
Seed telemetry events ONLY and explicitly trigger the PD materialization flow.

Flow:
telemetry_events → materialize_execution_from_telemetry → pd_executions → findings
"""

import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ------------------------------------------------------------
# Ensure `app.*` imports work
# ------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

# ------------------------------------------------------------
# Imports
# ------------------------------------------------------------
from app.db.connection import get_connection
from app.pd.materializer import materialize_execution_from_telemetry

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("seed.telemetry.flow")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ------------------------------------------------------------
# Insert telemetry (schema-correct)
# ------------------------------------------------------------
def insert_telemetry(correlation_request_id: str) -> None:
    event_id = str(uuid.uuid4())

    logger.info(
        "INSERT_TELEMETRY_EVENT",
        extra={
            "eventId": event_id,
            "correlationRequestId": correlation_request_id,
        },
    )

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO telemetry_events (
                event_id,
                event_type,
                event_layer,
                event_subtype,
                timestamp_utc,

                source_system,
                source_channel_id,
                source_environment,

                correlation_request_id,

                protocol_standard,
                protocol_interaction_id,

                status,
                duration_ms,

                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                "PD",
                "APPLICATION",
                "request.complete",
                utc_now(),

                "demo-emr",
                "pd-channel-01",
                "prod",

                correlation_request_id,

                "HL7",
                "ITI-55",

                "SUCCESS",
                420,

                "<PatientDiscoveryResponse>demo</PatientDiscoveryResponse>",
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    logger.info("TELEMETRY_FLOW_SEED_START")

    correlation_request_id = f"pd-{uuid.uuid4()}"

    logger.info(
        "NEW_LOGICAL_PD_REQUEST",
        extra={"correlationRequestId": correlation_request_id},
    )

    # 1️⃣ Insert telemetry events
    insert_telemetry(correlation_request_id)

    # 2️⃣ Deterministically materialize execution
    logger.info(
        "MATERIALIZE_PD_EXECUTION",
        extra={"correlationRequestId": correlation_request_id},
    )

    materialize_execution_from_telemetry(correlation_request_id)

    logger.info(
        "TELEMETRY_FLOW_COMPLETE",
        extra={"correlationRequestId": correlation_request_id},
    )


if __name__ == "__main__":
    main()
