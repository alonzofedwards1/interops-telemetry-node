"""Certificate provider abstractions for transport ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import requests


class CertificateProviderError(RuntimeError):
    """Raised when certificate retrieval fails."""


@dataclass(frozen=True)
class CertPayload:
    """Normalized certificate payload fetched from OpenHIM API."""

    fingerprint_sha1: str
    subject_cn: str | None
    issuer_cn: str | None
    not_before: datetime | None
    not_after: datetime | None
    pem: str | None
    source: str = "openhim_api"


class CertificateProvider(Protocol):
    """Abstraction for server certificate retrieval."""

    def get_server_cert(self) -> CertPayload:
        """Fetch and normalize the active server certificate."""


class OpenHIMApiCertificateProvider:
    """Fetches OpenHIM server certificate from `/keystore/cert`."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_tls: bool,
        timeout: int = 10,
        include_pem: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._verify_tls = verify_tls
        self._timeout = timeout
        self._include_pem = include_pem
        self._session = session or requests.Session()
        self._session.auth = (username, password)

    def get_server_cert(self) -> CertPayload:
        try:
            response = self._session.get(
                f"{self._base_url}/keystore/cert",
                verify=self._verify_tls,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CertificateProviderError(f"OpenHIM cert API request failed: {exc}") from exc

        payload = response.json()
        if not isinstance(payload, dict):
            raise CertificateProviderError("Unexpected certificate payload type")

        fingerprint = payload.get("fingerprint")
        if not fingerprint:
            raise CertificateProviderError("Certificate fingerprint missing in OpenHIM response")

        validity = payload.get("validity") or {}

        return CertPayload(
            fingerprint_sha1=str(fingerprint),
            subject_cn=_as_optional_str(payload.get("commonName")),
            issuer_cn=None,
            not_before=_parse_optional_datetime(validity.get("start")),
            not_after=_parse_optional_datetime(validity.get("end")),
            pem=_as_optional_str(payload.get("data")) if self._include_pem else None,
        )


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
