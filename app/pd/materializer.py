import json
import logging
import xml.etree.ElementTree as ElementTree
from datetime import datetime

from app.db.connection import get_connection
from app.findings.evaluator import evaluate_pd_execution
from app.oids.repository import register_observed_oid
from app.pd.models import PDExecution
from app.pd.store import upsert_execution

logger = logging.getLogger(__name__)


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _select_cert_status(transport_events: list[dict]) -> str:
    cert_rank = {
        "NOT_REPORTED": 0,
        "VALID": 1,
        "INVALID": 2,
        "EXPIRED": 2,
        "UNTRUSTED": 2,
    }
    statuses = [event.get("cert_status") for event in transport_events if event.get("cert_status")]
    if not statuses:
        return "NOT_REPORTED"

    selected = statuses[0]
    highest_rank = cert_rank.get(selected, 0)
    for status in statuses[1:]:
        rank = cert_rank.get(status, 0)
        if rank > highest_rank:
            selected = status
            highest_rank = rank
    return selected


def _select_cert_thumbprint(transport_events: list[dict]) -> str | None:
    for event in transport_events:
        thumbprint = event.get("cert_thumbprint")
        if thumbprint:
            return thumbprint
    return None


def _derive_failure_metadata(
    *,
    cert_status: str,
    outcome: str,
    transport_events: list[dict],
    application_events: list[dict],
) -> tuple[str | None, str | None, int | None]:
    if cert_status in ("INVALID", "EXPIRED", "UNTRUSTED"):
        root_cause_map = {
            "INVALID": "CERT_INVALID",
            "EXPIRED": "CERT_EXPIRED",
            "UNTRUSTED": "TRUST_ANCHOR",
        }
        return "SECURITY", root_cause_map[cert_status], None

    if any(event.get("status") == "TIMEOUT" for event in transport_events):
        return "TRANSPORT", "TIMEOUT", 504

    if outcome == "failure" and application_events:
        response_code = application_events[-1].get("pd_response_code")
        if response_code == "PNF":
            return "APPLICATION", "PNF", 200
        if response_code == "ERROR":
            return "APPLICATION", "UNKNOWN", 500
        return "APPLICATION", "UNKNOWN", 500

    if outcome == "success":
        return None, None, 200

    return None, None, None


def _extract_xml_from_payload(raw_payload: str | None) -> str | None:
    if not raw_payload:
        return None
    raw_payload = raw_payload.strip()
    if not raw_payload:
        return None
    if raw_payload.startswith("<"):
        return raw_payload
    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None

    def _find_xml(value: object) -> str | None:
        if isinstance(value, str):
            candidate = value.strip()
            if candidate.startswith("<") and ">" in candidate:
                return candidate
        if isinstance(value, dict):
            for item in value.values():
                found = _find_xml(item)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = _find_xml(item)
                if found:
                    return found
        return None

    return _find_xml(parsed)


def _extract_oids_from_xml(xml_payload: str | None) -> tuple[str | None, str | None]:
    if not xml_payload:
        return None, None
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None, None

    def _find_device_oid(role: str) -> str | None:
        for node in root.iter():
            if not node.tag.endswith(role):
                continue
            device_id = node.find(".//{*}device/{*}id")
            if device_id is None:
                continue
            oid = device_id.attrib.get("root")
            if oid:
                return oid
        return None

    return _find_device_oid("sender"), _find_device_oid("receiver")


def _register_oid_safe(oid: str | None) -> None:
    if not oid:
        return
    try:
        register_observed_oid(oid, None)
    except Exception:
        logger.exception("Failed to register observed OID", extra={"oid": oid})


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
            source_channel_id,
            source_environment,
            cert_status,
            cert_thumbprint,
            raw_payload
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
    source_oid = None
    target_oid = None
    for event in application_events:
        xml_payload = _extract_xml_from_payload(event["raw_payload"])
        source_oid, target_oid = _extract_oids_from_xml(xml_payload)
        if source_oid or target_oid:
            break

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

    transport_events = [r for r in rows if r["event_layer"] == "TRANSPORT"]
    cert_status = _select_cert_status(transport_events)
    cert_thumbprint = _select_cert_thumbprint(transport_events)
    failure_stage, root_cause, http_status = _derive_failure_metadata(
        cert_status=cert_status,
        outcome=outcome,
        transport_events=transport_events,
        application_events=application_events,
    )

    logger.info(
        "OID_ASSIGNMENT",
        extra={
            "requestId": request_id,
            "sourceOid": source_oid,
            "targetOid": target_oid,
        },
    )

    _register_oid_safe(source_oid)
    _register_oid_safe(target_oid)

    # ✅ STORE-CONTRACT-COMPLIANT UPSERT
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
        source_oid=source_oid,
        target_oid=target_oid,
        cert_status=cert_status,
        cert_thumbprint=cert_thumbprint,
        failure_stage=failure_stage,
        root_cause=root_cause,
        http_status=http_status,
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
        sourceOid=source_oid,
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
