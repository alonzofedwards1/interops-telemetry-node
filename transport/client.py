"""OpenHIM API client used for transaction retrieval."""

from __future__ import annotations

from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class OpenHIMClient:
    """Simple OpenHIM client for fetching transactions."""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.session = requests.Session()
        if username and password:
            self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update({"Accept": "application/json"})

    def get_transactions(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch a page of transactions from OpenHIM."""
        response = self.session.get(
            f"{self.base_url}/transactions",
            params={"limit": limit},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            if isinstance(payload.get("transactions"), list):
                return payload["transactions"]
            if isinstance(payload.get("data"), list):
                return payload["data"]
        raise ValueError("Unsupported OpenHIM transactions response format")

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        """Fetch a single transaction by ID from OpenHIM."""
        response = self.session.get(
            f"{self.base_url}/transactions/{transaction_id}",
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            if "transaction" in payload and isinstance(payload["transaction"], dict):
                return payload["transaction"]
            return payload
        raise ValueError("Unsupported OpenHIM transaction response format")
