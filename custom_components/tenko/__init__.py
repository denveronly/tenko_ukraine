"""Tenko electric boiler integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TenkoApi
from .const import CONF_LOGIN, CONF_TOKEN
from .coordinator import TenkoCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.NUMBER, Platform.SWITCH]

TenkoConfigEntry = ConfigEntry[TenkoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TenkoConfigEntry) -> bool:
    api = TenkoApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        login=entry.data.get(CONF_LOGIN),
        password=entry.data.get(CONF_PASSWORD),
        token=entry.data.get(CONF_TOKEN),
    )
    coordinator = TenkoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TenkoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
