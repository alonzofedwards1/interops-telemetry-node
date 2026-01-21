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
    Deterministically builds or updates a PD execution from telemetry_events
    for the given correlation_request_id.

    Store contract is authoritative.
    """

    logger.info(
        "PD_EXECUTION_MATERIALIZATION_START",
        extra={"requestId": request_id},
    )

    conn = get_connection()
    cur = conn.cursor()

    # ---------------------------------------------------------
    # Pull telemetry
    # ---------------------------------------------------------
    cur.execute(
        """
        SELECT
            event_id,
            timestamp_utc,
            event_layer,
            pd_response_code,
            pd_error_code,
            status,
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
        logger.warning(
            "PD_EXECUTION_MATERIALIZATION_SKIPPED",
            extra={
                "requestId": request_id,
                "reason": "no_telemetry",
            },
        )
        conn.close()
        return

    first = rows[0]
    last = rows[-1]

    # ---------------------------------------------------------
    # Derive execution facts
    # ---------------------------------------------------------
    started_at = _parse_ts(first["timestamp_utc"])
    completed_at = _parse_ts(last["timestamp_utc"])
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    event_count = len(rows)

    outcome = "failure"

    application_events = [r for r in rows if r["event_layer"] == "APPLICATION"]
    if application_events:
        last_app = application_events[-1]
        if last_app["pd_response_code"] == "SUCCESS":
            outcome = "success"

    cert_status = "NOT_REPORTED"
    cert_thumbprint = None
    failure_stage = "UNKNOWN"
    root_cause = "UNKNOWN"
    http_status = None

    if outcome == "success":
        http_status = 200
    elif application_events:
        last_app = application_events[-1]
        failure_stage = "APPLICATION"
        pd_response_code = last_app["pd_response_code"]
        pd_error_code = last_app["pd_error_code"]

        if pd_response_code == "PNF":
            root_cause = "PNF"
            http_status = 400
        elif pd_error_code:
            root_cause = pd_error_code
            http_status = 400 if pd_error_code == "MISSING_REQUIRED_ELEMENT" else 500
        else:
            root_cause = "UNKNOWN"
            http_status = 500
    elif transport_events:
        last_transport = transport_events[-1]
        failure_stage = "TRANSPORT"
        status = last_transport["status"]
        if status == "TIMEOUT":
            root_cause = "TIMEOUT"
            http_status = 504
        else:
            root_cause = "UNKNOWN"
            http_status = 500
    else:
        failure_stage = "UNKNOWN"
        root_cause = "UNKNOWN"
        http_status = 500

    # ✅ STORE-CONTRACT-COMPLIANT UPSERT
    upsert_execution(
        request_id=request_id,
        event_id=last["event_id"],
        started_at=started_at.isoformat().replace("+00:00", "Z"),
        completed_at=completed_at.isoformat().replace("+00:00", "Z"),
        duration_ms=duration_ms,
        outcome=outcome,
        source_channel_id=last["source_channel_id"],
        source_environment=last["source_environment"],
        source_oid=None,
        target_oid=None,
        cert_status=None,
        cert_thumbprint=None,
        failure_stage=None,
        root_cause=None,
        http_status=None,
    )

    conn.commit()
    conn.close()

    execution = PDExecution(
        requestId=request_id,
        startedAt=started_at.isoformat().replace("+00:00", "Z"),
        completedAt=completed_at.isoformat().replace("+00:00", "Z"),
        executionTimeMs=duration_ms,
        outcome=outcome,
        channelId=last["source_channel_id"],
        environment=last["source_environment"],
        certStatus="UNKNOWN",
        certThumbprint=None,
        failureStage=None,
        rootCause=None,
        httpStatus=None,
    )

    evaluate_pd_execution(execution)

    logger.info(
        "PD_EXECUTION_MATERIALIZATION_COMPLETE",
        extra={
            "requestId": request_id,
            "outcome": outcome,
            "eventCount": event_count,
        },
    )
