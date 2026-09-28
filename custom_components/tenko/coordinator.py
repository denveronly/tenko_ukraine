"""Data coordinator for Tenko."""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TenkoApi, TenkoAuthError, TenkoError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, GROUP_DEFAULTS, GROUP_ENDPOINT

_LOGGER = logging.getLogger(__name__)


class TenkoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /total_state and sends grouped commands."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TenkoApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        # Last known value of every command field. The API wants whole groups
        # (e.g. WF temp+delta together), so we always send the full group.
        self.commands: dict[str, dict[str, str]] = copy.deepcopy(GROUP_DEFAULTS)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.get_total_state()
        except TenkoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TenkoError as err:
            raise UpdateFailed(str(err)) from err

        # If the server reports current settings, use them as the source of truth.
        for group, fields in self.commands.items():
            reported = data.get(group)
            if isinstance(reported, dict):
                for key in fields:
                    if reported.get(key) is not None:
                        fields[key] = str(reported[key])
        return data

    def restore_field(self, group: str, key: str, value: str) -> None:
        """Seed a field from a restored entity state (only if still default)."""
        if self.commands[group][key] == GROUP_DEFAULTS[group][key]:
            self.commands[group][key] = value

    async def async_send(self, group: str, **changes: Any) -> None:
        """Send a full command group with some fields changed."""
        payload = {**self.commands[group], **{k: str(v) for k, v in changes.items()}}
        try:
            await self.api.post(GROUP_ENDPOINT[group], {group: payload})
        except TenkoAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Tenko auth failed: {err}") from err
        except TenkoError as err:
            raise HomeAssistantError(f"Tenko command failed: {err}") from err
        self.commands[group] = payload
        self.async_update_listeners()
