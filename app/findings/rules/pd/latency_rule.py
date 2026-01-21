from app.findings.models import FindingCreate
from app.findings.rules.base import FindingRule
from app.findings.rules.registry import register
from app.findings.utils import deterministic_finding_id
from app.pd.models import PDExecution


class PdLatencyRule(FindingRule):
    id = "PD_LATENCY"
    version = "v1"
    name = "PD Latency Threshold"
    category = "Latency"
    severity = "warning"

    THRESHOLD_MS = 2000

    def applies_to(self, execution: PDExecution) -> bool:
        return execution.executionTimeMs is not None

    def evaluate(self, execution: PDExecution) -> list[FindingCreate]:
        if execution.executionTimeMs <= self.THRESHOLD_MS:
            return []

        finding_id = deterministic_finding_id(
            rule_id=self.id,
            rule_version=self.version,
            execution_id=execution.requestId,
        )

        return [
            FindingCreate(
                id=finding_id,
                executionId=execution.requestId,
                executionType="PD",
                severity=self.severity,
                category=self.category,
                summary="PD execution exceeded latency threshold",
                technicalDetail=(
                    f"Duration {execution.executionTimeMs}ms exceeded "
                    f"{self.THRESHOLD_MS}ms"
                ),
                recommendedAction="Investigate downstream latency or retry behavior",
                status="open",
            )
        ]


register(PdLatencyRule())
