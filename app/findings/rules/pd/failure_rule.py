from app.findings.models import FindingCreate
from app.findings.rules.base import FindingRule
from app.findings.rules.registry import register
from app.findings.utils import deterministic_finding_id
from app.pd.models import PDExecution


class PdfailureRule(FindingRule):
    id = "PD_FAILURE"
    version = "v1"
    name = "PD Execution Failure"
    category = "Patient Discovery"
    severity = "critical"

    def applies_to(self, execution: PDExecution) -> bool:
        return execution.outcome == "failure"

    def evaluate(self, execution: PDExecution) -> list[FindingCreate]:
        finding_id = deterministic_finding_id(
            rule_id=self.id,
            rule_version=self.version,
            execution_id=execution.requestId,
        )
        technical_detail = (
            f"Outcome: {execution.outcome}, duration {execution.executionTimeMs}ms"
        )

        return [
            FindingCreate(
                id=finding_id,
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
