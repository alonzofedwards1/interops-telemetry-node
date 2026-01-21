import logging

from app.db.connection import get_connection
from app.findings.repository import (
    add_or_update_finding,
    delete_finding_by_id,
    find_finding_ids_by_signature,
    replace_finding_id,
)
from app.findings.rules import pd  # noqa: F401
from app.findings.rules.registry import get_rules
from app.pd.certificates import extract_transport_evidence
from app.pd.models import PDExecution
from app.pd.store import update_execution_cert_fields

logger = logging.getLogger(__name__)


def _load_transport_events(request_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT event_layer, status, raw_payload
            FROM telemetry_events
            WHERE correlation_request_id = ?
              AND event_type = 'PD'
              AND event_layer = 'TRANSPORT'
            ORDER BY timestamp_utc ASC
            """,
            (request_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def evaluate_pd_execution(execution: PDExecution) -> None:
    logger.info(
        "FINDINGS_EVALUATION_START",
        extra={"requestId": execution.requestId},
    )

    transport_events = _load_transport_events(execution.requestId)
    evidence = extract_transport_evidence(transport_events)
    if any(value is not None for value in evidence.values()):
        update_execution_cert_fields(
            request_id=execution.requestId,
            cert_status=evidence["cert_status"],
            cert_thumbprint=evidence["cert_thumbprint"],
            failure_stage=evidence["failure_stage"],
            root_cause=evidence["root_cause"],
            http_status=evidence["http_status"],
        )

    for rule in get_rules():
        if not rule.applies_to(execution):
            continue

        findings = rule.evaluate(execution)
        for finding in findings:
            existing_ids = find_finding_ids_by_signature(
                execution_id=finding.executionId,
                execution_type=finding.executionType,
                severity=finding.severity,
                category=finding.category,
                summary=finding.summary,
            )

            if existing_ids:
                if finding.id in existing_ids:
                    for existing_id in existing_ids:
                        if existing_id != finding.id:
                            delete_finding_by_id(existing_id)
                else:
                    primary_id = existing_ids[0]
                    replace_finding_id(current_id=primary_id, new_id=finding.id)
                    for existing_id in existing_ids[1:]:
                        delete_finding_by_id(existing_id)

            add_or_update_finding(
                id=finding.id,
                execution_id=finding.executionId,
                execution_type=finding.executionType,
                severity=finding.severity,
                category=finding.category,
                summary=finding.summary,
                technical_detail=finding.technicalDetail,
                recommended_action=finding.recommendedAction,
                status=finding.status,
            )

    logger.info(
        "FINDINGS_EVALUATION_COMPLETE",
        extra={"requestId": execution.requestId},
    )
