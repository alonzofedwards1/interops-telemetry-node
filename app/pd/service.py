import json

from app.pd.models import PDExecutionCount
from app.pd.store import count_executions, get_execution_telemetry_events, list_executions


def fetch_pd_executions():
    return list_executions()


def fetch_pd_execution_count() -> PDExecutionCount:
    return PDExecutionCount(count=count_executions())


def fetch_execution_telemetry(request_id: str) -> list[dict]:
    rows = get_execution_telemetry_events(request_id)

    events = []
    for row in rows:
        raw_payload = row["raw_payload"]
        parsed_raw = None
        if raw_payload:
            try:
                parsed_raw = json.loads(raw_payload)
            except (json.JSONDecodeError, TypeError):
                parsed_raw = raw_payload
        events.append(
            {
                "eventId": row["event_id"],
                "eventType": row["event_type"],
                "timestamp": row["timestamp_utc"],
                "source": {
                    "channelId": row["source_channel_id"],
                    "environment": row["source_environment"],
                },
                "outcome": {
                    "status": row["status"],
                    "durationMs": row["duration_ms"],
                },
                "correlation": {
                    "requestId": row["correlation_request_id"],
                },
                "raw": parsed_raw,
            }
        )

    return events
