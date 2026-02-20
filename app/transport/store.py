from typing import Any
from psycopg2.extras import Json

from app.db.connection import get_connection


class TransportEventStore:

    def upsert_event(self, event: dict[str, Any]) -> None:
        conn = get_connection()

        try:
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
                        timestamp,
                        cert_subject_cn,
                        cert_subject_san,
                        cert_issuer_cn,
                        cert_not_before,
                        cert_not_after,
                        cert_serial,
                        cert_sha256,
                        cert_status
                    )
                    VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s
                    )
                    ON CONFLICT (transaction_id)
                    DO UPDATE SET
                        channel = EXCLUDED.channel,
                        request_method = EXCLUDED.request_method,
                        request_url = EXCLUDED.request_url,
                        request_headers = EXCLUDED.request_headers,
                        response_status = EXCLUDED.response_status,
                        response_duration_ms = EXCLUDED.response_duration_ms,
                        source_ip = EXCLUDED.source_ip,
                        timestamp = EXCLUDED.timestamp,
                        cert_subject_cn = EXCLUDED.cert_subject_cn,
                        cert_subject_san = EXCLUDED.cert_subject_san,
                        cert_issuer_cn = EXCLUDED.cert_issuer_cn,
                        cert_not_before = EXCLUDED.cert_not_before,
                        cert_not_after = EXCLUDED.cert_not_after,
                        cert_serial = EXCLUDED.cert_serial,
                        cert_sha256 = EXCLUDED.cert_sha256,
                        cert_status = EXCLUDED.cert_status
                    """,
                    (
                        event.get("transaction_id"),
                        event.get("channel"),
                        event.get("request_method"),
                        event.get("request_url"),
                        Json(event.get("request_headers") or {}),
                        event.get("response_status"),
                        event.get("response_duration_ms"),
                        event.get("source_ip"),
                        event.get("timestamp"),
                        event.get("cert_subject_cn"),
                        event.get("cert_subject_san"),
                        event.get("cert_issuer_cn"),
                        event.get("cert_not_before"),
                        event.get("cert_not_after"),
                        event.get("cert_serial"),
                        event.get("cert_sha256"),
                        event.get("cert_status"),
                    ),
                )

            conn.commit()

        finally:
            conn.close()
