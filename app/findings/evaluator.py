import logging

from app.findings.repository import add_or_update_finding
from app.findings.rules import pd  # noqa: F401
from app.findings.rules.registry import get_rules
from app.pd.models import PDExecution

logger = logging.getLogger(__name__)


def evaluate_pd_execution(execution: PDExecution) -> None:
    logger.info(
        "FINDINGS_EVALUATION_START",
        extra={"requestId": execution.requestId},
    )

    for rule in get_rules():
        if not rule.applies_to(execution):
            continue

        findings = rule.evaluate(execution)
        for finding in findings:
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
