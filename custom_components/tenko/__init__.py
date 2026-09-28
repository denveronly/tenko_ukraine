"""Tenko electric boiler integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TenkoApi
from .const import CONF_TOKEN
from .coordinator import TenkoCoordinator
from .offpeak import OffPeakManager

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.TIME,
]

TenkoConfigEntry = ConfigEntry[TenkoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TenkoConfigEntry) -> bool:
    api = TenkoApi(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN])
    coordinator = TenkoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    coordinator.offpeak = OffPeakManager(hass, coordinator)
    await coordinator.offpeak.async_load()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.offpeak.async_start()
    entry.async_on_unload(coordinator.offpeak.async_stop)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: TenkoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TenkoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
