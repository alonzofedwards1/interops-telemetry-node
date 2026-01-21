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
def insert_event(
    conn,
    *,
    correlation_request_id: str,
    correlation_id: str,
    **kwargs,
) -> None:
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

            correlation_id,
            correlation_request_id,

            protocol_standard,
            protocol_interaction_id,

            status,
            duration_ms,

            -- 🔐 transport-level cert facts (nullable)
            cert_status,
            cert_thumbprint,

            pd_response_code,
            pd_error_code,
            missing_required_elements,

            raw_payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),

            # MUST match materializer expectations
            kwargs["event_type"],  # PD_REQUEST / PD_RESPONSE

            kwargs["event_layer"],
            kwargs["event_subtype"],
            utc_now(),

            # Chain of custody
            "MIRTH",
            "PD_Request_Outbound",
            "PROD",

            correlation_id,
            correlation_request_id,

            # Protocol truth
            "IHE",
            "ITI-55",

            kwargs.get("status"),
            kwargs.get("duration_ms"),

            # 🔐 cert facts (transport only)
            kwargs.get("cert_status"),
            kwargs.get("cert_thumbprint"),

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

    # Deterministic correlation_id for grouping
    correlation_id = correlation_request_id

    conn = get_connection()
    try:
        # 1️⃣ PD REQUEST — transport ingress with TLS cert observed
        insert_event(
            conn,
            correlation_request_id=correlation_request_id,
            correlation_id=correlation_id,
            event_type="PD_REQUEST",
            event_layer="TRANSPORT",
            event_subtype="INGEST_RECEIVED",
            status="SUCCESS",
            duration_ms=45,

            # 🔐 CERTIFICATE FACTS (REALISTIC)
            cert_status="VALID",
            cert_thumbprint="3A:F9:12:44:9B:88:EE:01:AA:BC:91:FE:10:22:77:99",

            raw_payload="<PRPA_IN201305UV02/>",
        )

        # 2️⃣ PD RESPONSE — application layer (NO_MATCH is still success)
        insert_event(
            conn,
            correlation_request_id=correlation_request_id,
            correlation_id=correlation_id,
            event_type="PD_RESPONSE",
            event_layer="APPLICATION",
            event_subtype="RESPONSE_PARSED",
            status="SUCCESS",
            duration_ms=420,
            pd_response_code="NO_MATCH",
            pd_error_code=None,
            missing_required_elements=None,
            raw_payload="""
                <PRPA_IN201306UV02>
                  <queryAck>
                    <queryResponseCode code="NF"/>
                  </queryAck>
                </PRPA_IN201306UV02>
            """.strip(),
        )

        # 3️⃣ PD RESPONSE — transport completion
        insert_event(
            conn,
            correlation_request_id=correlation_request_id,
            correlation_id=correlation_id,
            event_type="PD_RESPONSE",
            event_layer="TRANSPORT",
            event_subtype="RESPONSE_COMPLETE",
            status="SUCCESS",
            duration_ms=30,
            raw_payload="<HTTP 200 OK/>",
        )

        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main() -> None:
    logger.info("TELEMETRY_FLOW_SEED_START")

    correlation_request_id = f"urn:uuid:{uuid.uuid4()}"

    logger.info(
        "NEW_LOGICAL_PD_REQUEST",
        extra={"correlationRequestId": correlation_request_id},
    )

    # 1️⃣ Seed telemetry only
    insert_pd_telemetry_sequence(correlation_request_id)

    # 2️⃣ Explicitly materialize execution
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
