"""Async client for the Tenko cloud API."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import API_PREFIX, EP_AUTH, EP_TOTAL_STATE

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)


class TenkoError(Exception):
    """Generic API error."""


class TenkoAuthError(TenkoError):
    """Credentials or token rejected."""


class TenkoApi:
    """Tenko API client.

    Auth: either a ready bearer token, or login/password exchanged
    for a token via POST /auth. The token is never logged.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        *,
        login: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> None:
        self._session = session
        self._base = host.rstrip("/") + API_PREFIX
        self._login = login
        self._password = password
        self._token = token

    @property
    def can_reauth(self) -> bool:
        return bool(self._login and self._password)

    async def authenticate(self) -> str:
        """Exchange login/password for a token."""
        if not self.can_reauth:
            raise TenkoAuthError("No login/password to obtain a token")
        try:
            async with self._session.post(
                self._base + EP_AUTH,
                data={"login": self._login, "password": self._password},
                headers={"accept": "application/json"},
                timeout=TIMEOUT,
            ) as resp:
                text = await resp.text()
                if resp.status in (401, 403, 422):
                    raise TenkoAuthError(f"Auth rejected (HTTP {resp.status})")
                if resp.status >= 400:
                    raise TenkoError(f"Auth failed (HTTP {resp.status})")
        except aiohttp.ClientError as err:
            raise TenkoError(f"Connection error: {err}") from err

        try:
            token = json.loads(text).get("token")
        except (ValueError, AttributeError) as err:
            raise TenkoError("Unexpected /auth response") from err
        if not token:
            raise TenkoAuthError("No token in /auth response")
        self._token = token
        return token

    async def _request(
        self, method: str, endpoint: str, payload: dict[str, Any] | None = None, *, retry: bool = True
    ) -> Any:
        if not self._token:
            await self.authenticate()

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        try:
            async with self._session.request(
                method,
                self._base + endpoint,
                json=payload,
                headers=headers,
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    if retry and self.can_reauth:
                        self._token = None
                        return await self._request(method, endpoint, payload, retry=False)
                    raise TenkoAuthError(f"Token rejected (HTTP {resp.status})")
                text = await resp.text()
                if resp.status >= 400:
                    raise TenkoError(f"{method} {endpoint} failed (HTTP {resp.status}): {text[:200]}")
        except aiohttp.ClientError as err:
            raise TenkoError(f"Connection error: {err}") from err

        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return text

    async def get_total_state(self) -> dict[str, Any]:
        data = await self._request("GET", EP_TOTAL_STATE)
        if not isinstance(data, dict):
            raise TenkoError("Unexpected /total_state response")
        return data

    async def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        _LOGGER.debug("POST %s %s", endpoint, payload)
        return await self._request("POST", endpoint, payload)
