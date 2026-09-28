"""Button: fetch data from the server now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([TenkoRefreshButton(entry.runtime_data)])


class TenkoRefreshButton(TenkoEntity, ButtonEntity):
    _attr_name = "Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: TenkoCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
