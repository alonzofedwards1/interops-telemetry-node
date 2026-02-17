from __future__ import annotations

from typing import Any

import requests


class OpenHIMClient:

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 10,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

        if username and password:
            self.session.auth = (username, password)

    def get_transactions(self, limit: int = 100) -> list[dict[str, Any]]:
        url = f"{self.base_url}/transactions"
        response = self.session.get(url, params={"limit": limit}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("transactions", "results", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:

        url = f"{self.base_url}/transactions/{transaction_id}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        raise ValueError("Unexpected transaction payload type")
