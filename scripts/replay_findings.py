from app.findings.evaluator import evaluate_pd_execution
from app.pd.store import list_executions


def main() -> None:
    executions = list_executions(limit=100000)
    for execution in executions:
        evaluate_pd_execution(execution)


if __name__ == "__main__":
    main()
