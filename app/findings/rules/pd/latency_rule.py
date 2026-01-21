import uuid

from app.findings.models import FindingCreate
from app.findings.rules.base import FindingRule
from app.findings.rules.registry import register
from app.pd.models import PDExecution


class PdLatencyRule(FindingRule):
    id = "PD_LATENCY"
    name = "PD Latency Threshold"
    category = "Latency"
    severity = "warning"

    THRESHOLD_MS = 2000

    def applies_to(self, execution: PDExecution) -> bool:
        return execution.executionTimeMs is not None

    def evaluate(self, execution: PDExecution) -> list[FindingCreate]:
        if execution.executionTimeMs <= self.THRESHOLD_MS:
            return []

        return [
            FindingCreate(
                id=str(uuid.uuid4()),
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
