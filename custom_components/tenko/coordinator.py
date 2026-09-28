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
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EP_CONST_TEMP,
    EP_SETTINGS,
    EP_TOTAL_STATE,
    EP_USED_CHART,
    GROUP_COT,
    GROUP_DEFAULTS,
    GROUP_ENDPOINT,
    GROUP_MMT,
    GROUP_MOD,
    GROUP_PSS,
    GROUP_RWF,
    GROUP_STG,
    GROUP_USE,
    GROUP_WF,
)

_LOGGER = logging.getLogger(__name__)

# Which GET response carries the current value of each command group
SETTINGS_GROUPS = (GROUP_WF, GROUP_RWF, GROUP_STG, GROUP_PSS, GROUP_MMT, GROUP_MOD)


class TenkoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /total_state (+ settings) and sends commands.

    self.data = /total_state response (sensors).
    self.commands = current settings per group, read from /settings,
    /const_temp and /used_chart_type; used both for number/switch/select
    state and to build full-group POST payloads.
    """

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
        self.commands: dict[str, Any] = copy.deepcopy(GROUP_DEFAULTS)
        self.offpeak: Any = None  # OffPeakManager, set in async_setup_entry

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.api.get(EP_TOTAL_STATE)
            settings = await self.api.get(EP_SETTINGS)
            cot = await self.api.get(EP_CONST_TEMP)
            use = await self.api.get(EP_USED_CHART)
        except TenkoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TenkoError as err:
            raise UpdateFailed(str(err)) from err

        for group in SETTINGS_GROUPS:
            self._sync(group, settings.get(group))
        self._sync(GROUP_COT, cot.get(GROUP_COT))
        self._sync(GROUP_USE, use.get(GROUP_USE))
        return state

    def _sync(self, group: str, reported: Any) -> None:
        current = self.commands[group]
        if isinstance(current, dict):
            if isinstance(reported, dict):
                for key in current:
                    if reported.get(key) is not None:
                        current[key] = str(reported[key])
        elif reported is not None and not isinstance(reported, (dict, list)):
            self.commands[group] = str(reported)

    async def async_send(self, group: str, value: Any = None, **changes: Any) -> None:
        """Send a whole group: dict groups get `changes` merged, string groups get `value`."""
        current = self.commands[group]
        if isinstance(current, dict):
            payload: Any = {**current, **{k: str(v) for k, v in changes.items()}}
        else:
            payload = str(value)
        try:
            await self.api.post(GROUP_ENDPOINT[group], {group: payload})
        except TenkoAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Tenko auth failed: {err}") from err
        except TenkoError as err:
            raise HomeAssistantError(f"Tenko command failed: {err}") from err
        self.commands[group] = payload
        self.async_update_listeners()
