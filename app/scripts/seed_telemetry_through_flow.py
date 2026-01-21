"""
Seed telemetry events ONLY and explicitly trigger the PD materialization flow.

Flow:
telemetry_events
  → materialize_execution_from_telemetry
      → pd_executions
          → findings
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
# Insert a single telemetry event
# ------------------------------------------------------------
def insert_event(conn, *, correlation_request_id: str, **kwargs) -> None:
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

            pd_response_code,
            pd_error_code,
            missing_required_elements,

            raw_payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            "PD",
            kwargs["event_layer"],
            kwargs["event_subtype"],
            utc_now(),

            "demo-emr",
            "pd-channel-01",
            "prod",

            correlation_request_id,

            "HL7",
            "ITI-55",

            kwargs.get("status"),
            kwargs.get("duration_ms"),

            kwargs.get("pd_response_code"),
            kwargs.get("pd_error_code"),
            kwargs.get("missing_required_elements"),

            kwargs.get("raw_payload", "<PD/>"),
        ),
    )


# ------------------------------------------------------------
# Insert a realistic PD telemetry sequence
# ------------------------------------------------------------
def insert_pd_telemetry_sequence(correlation_request_id: str) -> None:
    logger.info(
        "INSERT_TELEMETRY_SEQUENCE",
        extra={"correlationRequestId": correlation_request_id},
    )

    conn = get_connection()
    try:
        # 1️⃣ Transport request sent
        insert_event(
            conn,
            correlation_request_id=correlation_request_id,
            event_layer="TRANSPORT",
            event_subtype="request.sent",
            status="SUCCESS",
            duration_ms=45,
        )

        # 2️⃣ Application response (failure: patient not found)
        insert_event(
            conn,
            correlation_request_id=correlation_request_id,
            event_layer="APPLICATION",
            event_subtype="response.received",
            status="FAILURE",
            duration_ms=420,
            pd_response_code="PNF",
            pd_error_code="PATIENT_NOT_FOUND",
            missing_required_elements=None,
            raw_payload="<PatientDiscoveryResponse><PNF/></PatientDiscoveryResponse>",
        )

        # 3️⃣ Transport response completed
        insert_event(
            conn,
            correlation_request_id=correlation_request_id,
            event_layer="TRANSPORT",
            event_subtype="response.complete",
            status="SUCCESS",
            duration_ms=30,
        )

        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main() -> None:
    logger.info("TELEMETRY_FLOW_SEED_START")

    correlation_request_id = f"pd-{uuid.uuid4()}"

    logger.info(
        "NEW_LOGICAL_PD_REQUEST",
        extra={"correlationRequestId": correlation_request_id},
    )

    # 1️⃣ Seed telemetry
    insert_pd_telemetry_sequence(correlation_request_id)

    # 2️⃣ Materialize execution
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
