from typing import Optional, Dict, Any
from psycopg2.extras import Json


def upsert_transport_event(
    conn,
    transaction_id: str,
    channel: str,
    request_method: str,
    request_url: str,
    request_headers: Dict[str, Any],
    response_status: int,
    response_duration_ms: int,
    source_ip: Optional[str],
    timestamp,
) -> None:
    """
    Upserts a transport event into transport_events table.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO transport_events (
                transaction_id,
                channel,
                request_method,
                request_url,
                request_headers,
                response_status,
                response_duration_ms,
                source_ip,
                timestamp
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (transaction_id)
            DO UPDATE SET
                channel = EXCLUDED.channel,
                request_method = EXCLUDED.request_method,
                request_url = EXCLUDED.request_url,
                request_headers = EXCLUDED.request_headers,
                response_status = EXCLUDED.response_status,
                response_duration_ms = EXCLUDED.response_duration_ms,
                source_ip = EXCLUDED.source_ip,
                timestamp = EXCLUDED.timestamp
            """,
            (
                transaction_id,
                channel,
                request_method,
                request_url,
                Json(request_headers),  # Correct JSON handling for Postgres
                response_status,
                response_duration_ms,
                source_ip,
                timestamp,
            ),
        )
