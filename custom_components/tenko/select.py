"""Select: which temperature program the boiler uses."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .const import CHART_TYPES, GROUP_USE
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([TenkoChartSelect(entry.runtime_data)])


class TenkoChartSelect(TenkoEntity, SelectEntity):
    """Temp = constant temperature, WChart = weekly chart, DChart = daily chart."""

    _attr_name = "Program"
    _attr_icon = "mdi:calendar-clock"
    _attr_options = list(CHART_TYPES)

    def __init__(self, coordinator: TenkoCoordinator) -> None:
        super().__init__(coordinator, "used_chart_type")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.commands[GROUP_USE]
        return value if value in CHART_TYPES else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_send(GROUP_USE, option)
