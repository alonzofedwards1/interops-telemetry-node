from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psycopg2 import Error
from psycopg2.extras import Json

from app.db.connection import get_connection
from app.transport.certificate_provider import CertPayload


@dataclass(frozen=True)
class EndpointInput:
    name: str
    host: str
    port: int
    scheme: str
    service_type: str


class TransportEventStore:

    def transaction_exists(self, transaction_id: str) -> bool:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM transport_events WHERE transaction_id = %s LIMIT 1",
                    (transaction_id,),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    def upsert_endpoint(self, endpoint: EndpointInput) -> int:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO endpoints (name, host, port, scheme, service_type, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (scheme, host, port)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        service_type = EXCLUDED.service_type,
                        updated_at = NOW()
                    RETURNING endpoint_id
                    """,
                    (endpoint.name, endpoint.host, endpoint.port, endpoint.scheme, endpoint.service_type),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0])
        except Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_certificate(self, cert: CertPayload) -> int:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO certificates (
                        fingerprint_sha1,
                        subject_cn,
                        issuer_cn,
                        not_before,
                        not_after,
                        pem,
                        first_seen_at,
                        last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (fingerprint_sha1)
                    DO UPDATE SET
                        subject_cn = EXCLUDED.subject_cn,
                        issuer_cn = EXCLUDED.issuer_cn,
                        not_before = EXCLUDED.not_before,
                        not_after = EXCLUDED.not_after,
                        pem = COALESCE(EXCLUDED.pem, certificates.pem),
                        last_seen_at = NOW()
                    RETURNING cert_id
                    """,
                    (
                        cert.fingerprint_sha1,
                        cert.subject_cn,
                        cert.issuer_cn,
                        cert.not_before,
                        cert.not_after,
                        cert.pem,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0])
        except Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    def insert_endpoint_cert_observation(
        self,
        endpoint_id: int,
        cert_id: int,
        source: str = "openhim_api",
        observed_at: datetime | None = None,
    ) -> None:
        conn = get_connection()
        observed_at = observed_at or datetime.now(timezone.utc)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO endpoint_cert_observations (
                        endpoint_id,
                        cert_id,
                        observed_at,
                        source
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (endpoint_id, cert_id, observed_at, source),
                )
            conn.commit()
        except Error:
            conn.rollback()
            raise
        finally:
            conn.close()

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
                        cert_status,
                        endpoint_id,
                        cert_id
                    )
                    VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
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
                        cert_status = EXCLUDED.cert_status,
                        endpoint_id = EXCLUDED.endpoint_id,
                        cert_id = EXCLUDED.cert_id
                    """,
                    (
                        event.get("transaction_id"),
                        event.get("channel"),
                        event.get("request_method"),
                        event.get("request_url"),
                        Json(event.get("request_headers") or {}),
                        int(event.get("response_status") or 0),
                        int(event.get("response_duration_ms") or 0),
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
                        event.get("endpoint_id"),
                        event.get("cert_id"),
                    ),
                )

            conn.commit()

        except Error:
            conn.rollback()
            raise

        finally:
            conn.close()
