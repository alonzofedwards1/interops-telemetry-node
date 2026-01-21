import hashlib


def deterministic_finding_id(
    *,
    rule_id: str,
    execution_id: str,
    rule_version: str = "v1",
) -> str:
    raw = f"{rule_id}:{rule_version}:{execution_id}"
    return hashlib.sha256(raw.encode()).hexdigest()
