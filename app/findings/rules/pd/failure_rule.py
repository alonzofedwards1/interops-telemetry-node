import uuid

from app.findings.models import FindingCreate
from app.findings.rules.base import FindingRule
from app.findings.rules.registry import register
from app.pd.models import PDExecution


class PdfailureRule(FindingRule):
    id = "PD_FAILURE"
    name = "PD Execution Failure"
    category = "Patient Discovery"
    severity = "critical"

    def applies_to(self, execution: PDExecution) -> bool:
        return execution.outcome == "failure"

    def evaluate(self, execution: PDExecution) -> list[FindingCreate]:
        technical_detail = (
            f"Outcome: {execution.outcome}, duration {execution.executionTimeMs}ms"
        )

        return [
            FindingCreate(
                id=str(uuid.uuid4()),
                executionId=execution.requestId,
                executionType="PD",
                severity=self.severity,
                category=self.category,
                summary="Patient Discovery execution failed",
                technicalDetail=technical_detail,
                recommendedAction=(
                    "Inspect downstream system behavior, retry logic, or payload structure"
                ),
                status="open",
            )
        ]


register(PdfailureRule())
