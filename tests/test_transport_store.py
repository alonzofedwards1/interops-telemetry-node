from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

psycopg2_stub = types.ModuleType("psycopg2")
psycopg2_stub.Error = Exception
extras_stub = types.ModuleType("psycopg2.extras")
extras_stub.Json = lambda value: value
extras_stub.DictCursor = object
psycopg2_stub.extras = extras_stub
psycopg2_stub.connect = lambda *args, **kwargs: None
sys.modules.setdefault("psycopg2", psycopg2_stub)
sys.modules.setdefault("psycopg2.extras", extras_stub)

from app.transport.certificate_provider import CertPayload
from app.transport.store import EndpointInput, TransportEventStore


class _FakeCursor:
    def __init__(self, fetch_value=(1,)) -> None:
        self.fetch_value = fetch_value
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.fetch_value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, fetch_value=(1,)) -> None:
        self.cursor_obj = _FakeCursor(fetch_value)

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class TransportStoreTests(unittest.TestCase):
    def test_upsert_endpoint_returns_same_id(self) -> None:
        conn = _FakeConn(fetch_value=(123,))
        with patch("app.transport.store.get_connection", return_value=conn):
            store = TransportEventStore()
            endpoint_id = store.upsert_endpoint(
                EndpointInput(name="openhim-core", host="localhost", port=5001, scheme="https", service_type="openhim")
            )

        self.assertEqual(endpoint_id, 123)
        self.assertIn("ON CONFLICT (scheme, host, port)", conn.cursor_obj.queries[0][0])

    def test_upsert_certificate_returns_same_id(self) -> None:
        conn = _FakeConn(fetch_value=(321,))
        with patch("app.transport.store.get_connection", return_value=conn):
            store = TransportEventStore()
            cert_id = store.upsert_certificate(
                CertPayload(
                    fingerprint_sha1="AA:BB",
                    subject_cn="openhim.local",
                    issuer_cn=None,
                    not_before=datetime.now(timezone.utc),
                    not_after=datetime.now(timezone.utc),
                    pem="pem",
                )
            )

        self.assertEqual(cert_id, 321)
        self.assertIn("ON CONFLICT (fingerprint_sha1)", conn.cursor_obj.queries[0][0])

    def test_insert_observation_executes_insert(self) -> None:
        conn = _FakeConn()
        with patch("app.transport.store.get_connection", return_value=conn):
            store = TransportEventStore()
            store.insert_endpoint_cert_observation(endpoint_id=10, cert_id=20)

        self.assertIn("INSERT INTO endpoint_cert_observations", conn.cursor_obj.queries[0][0])

    def test_upsert_event_accepts_nullable_cert_id(self) -> None:
        conn = _FakeConn()
        with patch("app.transport.store.get_connection", return_value=conn):
            store = TransportEventStore()
            store.upsert_event(
                {
                    "transaction_id": "tx-http",
                    "channel": "channel",
                    "request_method": "GET",
                    "request_url": "http://service.local",
                    "request_headers": {},
                    "response_status": 200,
                    "response_duration_ms": 10,
                    "source_ip": "127.0.0.1",
                    "timestamp": datetime.now(timezone.utc),
                    "endpoint_id": 11,
                    "cert_id": None,
                }
            )

        params = conn.cursor_obj.queries[0][1]
        self.assertEqual(params[-2], 11)
        self.assertIsNone(params[-1])


if __name__ == "__main__":
    unittest.main()
