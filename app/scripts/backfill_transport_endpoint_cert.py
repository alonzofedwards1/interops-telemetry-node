from __future__ import annotations

import logging

from app.db.connection import get_connection
from app.transport.certificate_provider import CertificateProviderError
from app.transport.ingest_openhim import TRANSPORT_CONFIG, _build_certificate_provider
from app.transport.store import EndpointInput, TransportEventStore

logger = logging.getLogger(__name__)


def run_backfill() -> None:
    store = TransportEventStore()
    endpoint_id = store.upsert_endpoint(
        EndpointInput(
            name="openhim-core",
            host=TRANSPORT_CONFIG.tls_host,
            port=TRANSPORT_CONFIG.tls_port,
            scheme="https",
            service_type="openhim",
        )
    )

    cert_id = None
    try:
        cert_payload = _build_certificate_provider().get_server_cert()
        cert_id = store.upsert_certificate(cert_payload)
        store.insert_endpoint_cert_observation(endpoint_id=endpoint_id, cert_id=cert_id, source=cert_payload.source)
    except CertificateProviderError as exc:
        logger.warning("transport_backfill_certificate_fetch_failed", extra={"error": str(exc)})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if cert_id is None:
                cur.execute(
                    """
                    UPDATE transport_events
                    SET endpoint_id = %s
                    WHERE endpoint_id IS NULL
                      AND request_url ILIKE 'https://%%'
                    """,
                    (endpoint_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE transport_events
                    SET endpoint_id = COALESCE(endpoint_id, %s),
                        cert_id = COALESCE(cert_id, %s)
                    WHERE request_url ILIKE 'https://%%'
                      AND (endpoint_id IS NULL OR cert_id IS NULL)
                    """,
                    (endpoint_id, cert_id),
                )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_backfill()
