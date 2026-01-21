"""
Replay findings evaluation for existing PD executions.

Flow:
pd_executions → rules engine → findings (idempotent)
"""

import sys
import logging
from pathlib import Path

# ------------------------------------------------------------
# Ensure `app.*` imports work when run as a script
# ------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

# ------------------------------------------------------------
# Imports (now safe)
# ------------------------------------------------------------
from app.findings.evaluator import evaluate_pd_execution
from app.pd.store import list_executions

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("replay.findings")


def main() -> None:
    logger.info("FINDINGS_REPLAY_START")

    executions = list_executions(limit=100_000)

    logger.info(
        "EXECUTIONS_LOADED",
        extra={"count": len(executions)},
    )

    for execution in executions:
        logger.info(
            "EVALUATE_EXECUTION",
            extra={"requestId": execution.requestId},
        )
        evaluate_pd_execution(execution)

    logger.info("FINDINGS_REPLAY_COMPLETE")


if __name__ == "__main__":
    main()
