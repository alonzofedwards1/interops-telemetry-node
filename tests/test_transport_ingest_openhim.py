from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import sys
import types

psycopg2_stub = types.ModuleType("psycopg2")
psycopg2_stub.Error = Exception
extras_stub = types.ModuleType("psycopg2.extras")
extras_stub.Json = lambda value: value
extras_stub.DictCursor = object
psycopg2_stub.extras = extras_stub
psycopg2_stub.connect = lambda *args, **kwargs: None
sys.modules.setdefault("psycopg2", psycopg2_stub)
sys.modules.setdefault("psycopg2.extras", extras_stub)

from app.transport.certificate_provider import CertPayload, CertificateProviderError
from app.transport.ingest_openhim import process_openhim_transaction


class _FakeCertProvider:
    def __init__(self, payload: CertPayload | None = None, raises: Exception | None = None) -> None:
        self.payload = payload
        self.raises = raises

    def get_server_cert(self) -> CertPayload:
        if self.raises:
            raise self.raises
        assert self.payload is not None
        return self.payload


class _FakeStore:
    last_instance: "_FakeStore" | None = None

    def __init__(self) -> None:
        self.__class__.last_instance = self
        self.event_rows = []
        self.observations = []

    def transaction_exists(self, transaction_id: str) -> bool:
        return False

    def upsert_endpoint(self, endpoint):
        self.endpoint = endpoint
        return 42

    def upsert_certificate(self, cert):
        self.cert = cert
        return 84

    def insert_endpoint_cert_observation(self, endpoint_id: int, cert_id: int, source: str = "openhim_api"):
        self.observations.append((endpoint_id, cert_id, source))

    def upsert_event(self, event_row):
        self.event_rows.append(event_row)


class ProcessOpenHIMTransactionTests(unittest.TestCase):
    @patch("app.transport.ingest_openhim.TransportEventStore", _FakeStore)
    def test_process_sets_endpoint_and_cert_ids_on_event(self) -> None:
        provider = _FakeCertProvider(
            payload=CertPayload(
                fingerprint_sha1="AA",
                subject_cn="openhim",
                issuer_cn=None,
                not_before=datetime.now(timezone.utc),
                not_after=datetime.now(timezone.utc),
                pem="pem",
            )
        )

        tx_id, skipped = process_openhim_transaction(
            {
                "transactionID": "tx-1",
                "channelID": "ch-1",
                "request": {"method": "GET", "path": "/test", "headers": {}},
                "response": {"status": 200, "duration": 5},
            },
            cert_provider=provider,
        )

        self.assertEqual(tx_id, "tx-1")
        self.assertFalse(skipped)
        store = _FakeStore.last_instance
        assert store is not None
        self.assertEqual(len(store.event_rows), 1)
        self.assertEqual(store.event_rows[0]["endpoint_id"], 42)
        self.assertEqual(store.event_rows[0]["cert_id"], 84)
        self.assertEqual(store.observations, [(42, 84, "openhim_api")])

    @patch("app.transport.ingest_openhim.TransportEventStore", _FakeStore)
    def test_process_keeps_cert_id_null_when_provider_fails(self) -> None:
        provider = _FakeCertProvider(raises=CertificateProviderError("unreachable"))

        tx_id, skipped = process_openhim_transaction(
            {
                "transactionID": "tx-2",
                "channelID": "ch-2",
                "request": {"method": "GET", "path": "http://service.local/test", "headers": {}},
                "response": {"status": 200, "duration": 5},
            },
            cert_provider=provider,
        )

        self.assertEqual(tx_id, "tx-2")
        self.assertFalse(skipped)
        store = _FakeStore.last_instance
        assert store is not None
        self.assertEqual(store.event_rows[0]["endpoint_id"], 42)
        self.assertIsNone(store.event_rows[0]["cert_id"])
        self.assertEqual(store.observations, [])


if __name__ == "__main__":
    unittest.main()


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class IngestOpenHIMTransactionsTests(unittest.TestCase):
    @patch("app.transport.ingest_openhim.process_openhim_transaction")
    @patch("app.transport.ingest_openhim.requests.get")
    def test_pull_supports_results_envelope(self, mock_get, mock_process) -> None:
        from app.transport.ingest_openhim import ingest_openhim_transactions

        mock_get.side_effect = [
            _FakeResponse(200, {"results": [{"_id": "tx-1", "request": {}, "response": {}}]}),
            _FakeResponse(200, {"results": []}),
        ]
        mock_process.return_value = ("tx-1", False)

        result = ingest_openhim_transactions(limit=1)

        self.assertEqual(result, {"processed": 1, "skipped": 0})
        self.assertEqual(mock_process.call_count, 1)

    @patch("app.transport.ingest_openhim.process_openhim_transaction")
    @patch("app.transport.ingest_openhim.requests.get")
    def test_pull_counts_processing_exceptions_as_skipped(self, mock_get, mock_process) -> None:
        from app.transport.ingest_openhim import ingest_openhim_transactions

        mock_get.side_effect = [
            _FakeResponse(200, {"transactions": [{"_id": "tx-1", "request": {}, "response": {}}]}),
            _FakeResponse(200, {"transactions": []}),
        ]
        mock_process.side_effect = RuntimeError("db down")

        result = ingest_openhim_transactions(limit=1)

        self.assertEqual(result, {"processed": 0, "skipped": 1})
