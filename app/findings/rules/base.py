from abc import ABC, abstractmethod
from typing import Iterable

from app.findings.models import FindingCreate
from app.pd.models import PDExecution


class FindingRule(ABC):
    id: str
    version: str = "v1"
    name: str
    category: str
    severity: str

    @abstractmethod
    def applies_to(self, execution: PDExecution) -> bool:
        """Return True if this rule should run for this execution."""

    @abstractmethod
    def evaluate(self, execution: PDExecution) -> Iterable[FindingCreate]:
        """Return zero or more findings."""
