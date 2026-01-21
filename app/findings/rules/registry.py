from app.findings.rules.base import FindingRule

_RULES: list[FindingRule] = []


def register(rule: FindingRule) -> None:
    _RULES.append(rule)


def get_rules() -> list[FindingRule]:
    return list(_RULES)
