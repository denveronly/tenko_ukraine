"""Async client for the Tenko cloud API (https://my.tenko.ua/api/)."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import API_PREFIX, EP_AUTH

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)


class TenkoError(Exception):
    """Generic API error."""


class TenkoAuthError(TenkoError):
    """Credentials or token rejected."""


def _api_url(host: str, endpoint: str, version: str = API_PREFIX) -> str:
    return host.rstrip("/") + version + endpoint


async def async_get_token(
    session: aiohttp.ClientSession, host: str, login: str, password: str
) -> str:
    """POST /auth with login/password -> token (one token per user and boiler).

    The password is used only here and is never stored.
    """
    try:
        async with session.post(
            _api_url(host, EP_AUTH),
            data={"login": login, "password": password},
            headers={"accept": "application/json"},
            timeout=TIMEOUT,
        ) as resp:
            text = await resp.text()
            status = resp.status
    except aiohttp.ClientError as err:
        raise TenkoError(f"Connection error: {err}") from err

    try:
        body = json.loads(text)
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}

    if status in (400, 401, 403, 422) or body.get("status") == "error":
        raise TenkoAuthError(body.get("message") or f"Auth rejected (HTTP {status})")
    if status >= 400:
        raise TenkoError(f"Auth failed (HTTP {status})")
    token = body.get("token")
    if not token:
        raise TenkoAuthError("No token in /auth response")
    return token


class TenkoApi:
    """Tenko API client working with a stored bearer token. The token is never logged."""

    def __init__(self, session: aiohttp.ClientSession, host: str, token: str) -> None:
        self._session = session
        self._host = host
        self._token = token

    async def _request(
        self, method: str, endpoint: str, payload: Any = None, version: str = API_PREFIX
    ) -> Any:
        try:
            async with self._session.request(
                method,
                _api_url(self._host, endpoint, version),
                json=payload,
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
                timeout=TIMEOUT,
            ) as resp:
                text = await resp.text()
                if resp.status in (401, 403):
                    raise TenkoAuthError(f"Token rejected (HTTP {resp.status})")
                if resp.status >= 400:
                    raise TenkoError(f"{method} {endpoint} failed (HTTP {resp.status})")
        except aiohttp.ClientError as err:
            raise TenkoError(f"Connection error: {err}") from err

        if not text:
            return None
        try:
            data = json.loads(text)
        except ValueError as err:
            raise TenkoError(f"{method} {endpoint}: non-JSON response") from err
        if isinstance(data, dict) and data.get("status") == "error":
            raise TenkoError(f"{method} {endpoint}: {data.get('message')}")
        return data

    async def get(self, endpoint: str) -> dict[str, Any]:
        data = await self._request("GET", endpoint)
        if not isinstance(data, dict):
            raise TenkoError(f"Unexpected {endpoint} response")
        return data

    async def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        _LOGGER.debug("POST %s %s", endpoint, payload)
        return await self._request("POST", endpoint, payload)
