import logging
from datetime import datetime

from app.db.connection import get_connection
from app.findings.evaluator import evaluate_pd_execution
from app.pd.models import PDExecution
from app.pd.store import upsert_execution

logger = logging.getLogger(__name__)


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def materialize_execution_from_telemetry(request_id: str) -> None:
    """
    Deterministically build a PD execution from telemetry.

    Rules:
    - Telemetry = facts
    - Execution = interpretation
    - Findings = escalation
    """

    logger.info(
        "PD_EXECUTION_MATERIALIZATION_START",
        extra={"requestId": request_id},
    )

    conn = get_connection()
    cur = conn.cursor()

    # ---------------------------------------------------------
    # Pull PD telemetry
    # ---------------------------------------------------------
    cur.execute(
        """
        SELECT
            event_id,
            timestamp_utc,
            event_layer,
            status,
            pd_response_code,
            pd_error_code,
            cert_status,
            cert_thumbprint,
            source_channel_id,
            source_environment
        FROM telemetry_events
        WHERE correlation_request_id = ?
          AND event_type = 'PD'
        ORDER BY timestamp_utc ASC
        """,
        (request_id,),
    )

    rows = cur.fetchall()
    if not rows:
        conn.close()
        return

    first = rows[0]
    last = rows[-1]

    started_at = _parse_ts(first["timestamp_utc"])
    completed_at = _parse_ts(last["timestamp_utc"])
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    transport_events = [r for r in rows if r["event_layer"] == "TRANSPORT"]
    application_events = [r for r in rows if r["event_layer"] == "APPLICATION"]

    # ---------------------------------------------------------
    # Certificate facts (transport-only)
    # ---------------------------------------------------------
    cert_status = "NOT_REPORTED"
    cert_thumbprint = None

    for ev in transport_events:
        if ev["cert_status"]:
            cert_status = ev["cert_status"]
        if ev["cert_thumbprint"]:
            cert_thumbprint = ev["cert_thumbprint"]

    # ---------------------------------------------------------
    # Outcome + Failure Stage + Root Cause
    # ---------------------------------------------------------
    outcome = "failure"  # must be lowercase
    failure_stage = None
    root_cause = None
    http_status = None

    if application_events:
        last_app = application_events[-1]
        pd_response_code = last_app["pd_response_code"]
        pd_error_code = last_app["pd_error_code"]

        # PD semantics: no patient found is still a success
        if pd_response_code in ("PNF", "NO_MATCH", "OK"):
            outcome = "success"
            http_status = 200
        else:
            outcome = "failure"
            failure_stage = "APPLICATION"
            root_cause = pd_error_code or pd_response_code or "UNKNOWN"
            http_status = 500

    elif transport_events:
        last_transport = transport_events[-1]
        outcome = "failure"
        failure_stage = "TRANSPORT"
        root_cause = last_transport["status"] or "UNKNOWN"
        http_status = 504 if root_cause == "TIMEOUT" else 500

    # Security escalation (certs override stage if bad)
    if cert_status in ("INVALID", "EXPIRED", "UNTRUSTED"):
        outcome = "failure"
        failure_stage = "SECURITY"
        root_cause = f"CERT_{cert_status}"
        http_status = 495  # TLS cert error (non-standard but common)

    # ---------------------------------------------------------
    # Persist execution
    # ---------------------------------------------------------
    upsert_execution(
        request_id=request_id,
        event_id=last["event_id"],
        started_at=started_at.isoformat().replace("+00:00", "Z"),
        completed_at=completed_at.isoformat().replace("+00:00", "Z"),
        duration_ms=duration_ms,
        outcome=outcome,
        transaction_type="PD",
        source_channel_id=last["source_channel_id"],
        source_environment=last["source_environment"],
        source_oid=None,
        target_oid=None,
        cert_status=cert_status,
        cert_thumbprint=cert_thumbprint,
        failure_stage=failure_stage,
        root_cause=root_cause,
        http_status=http_status,
    )

    conn.commit()
    conn.close()

    # ---------------------------------------------------------
    # Findings evaluation (may escalate cert / root cause)
    # ---------------------------------------------------------
    execution = PDExecution(
        requestId=request_id,
        startedAt=started_at.isoformat().replace("+00:00", "Z"),
        completedAt=completed_at.isoformat().replace("+00:00", "Z"),
        executionTimeMs=duration_ms,
        outcome=outcome,
        channelId=last["source_channel_id"],
        environment=last["source_environment"],
        certStatus=cert_status,
        certThumbprint=cert_thumbprint,
        failureStage=failure_stage,
        rootCause=root_cause,
        httpStatus=http_status,
    )

    evaluate_pd_execution(execution)

    logger.info(
        "PD_EXECUTION_MATERIALIZATION_COMPLETE",
        extra={
            "requestId": request_id,
            "outcome": outcome,
            "failureStage": failure_stage,
            "certStatus": cert_status,
        },
    )
