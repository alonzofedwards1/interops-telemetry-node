from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import Mock

from app.transport.certificate_provider import OpenHIMApiCertificateProvider


class OpenHIMApiCertificateProviderTests(unittest.TestCase):
    def test_get_server_cert_maps_response_fields(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "fingerprint": "AA:BB:CC",
            "commonName": "openhim.local",
            "validity": {
                "start": "2025-01-01T00:00:00Z",
                "end": "2026-01-01T00:00:00Z",
            },
            "data": "-----BEGIN CERTIFICATE-----...",
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = OpenHIMApiCertificateProvider(
            base_url="https://localhost:8080",
            username="user",
            password="pass",
            verify_tls=False,
            session=session,
        )

        cert = provider.get_server_cert()

        self.assertEqual(cert.fingerprint_sha1, "AA:BB:CC")
        self.assertEqual(cert.subject_cn, "openhim.local")
        self.assertIsNone(cert.issuer_cn)
        self.assertIsInstance(cert.not_before, datetime)
        self.assertIsInstance(cert.not_after, datetime)
        self.assertEqual(cert.pem, "-----BEGIN CERTIFICATE-----...")
        self.assertEqual(cert.source, "openhim_api")
        session.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
