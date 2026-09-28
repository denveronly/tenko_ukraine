"""Off-peak window start/end (editable times, stored in HA)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            TenkoOffPeakTime(coordinator, "start", "Off-peak start", "mdi:clock-start"),
            TenkoOffPeakTime(coordinator, "end", "Off-peak end", "mdi:clock-end"),
        ]
    )


class TenkoOffPeakTime(TenkoEntity, TimeEntity):
    def __init__(self, coordinator: TenkoCoordinator, field: str, name: str, icon: str) -> None:
        super().__init__(coordinator, f"off_peak_{field}")
        self._field = field
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> time:
        return getattr(self.coordinator.offpeak, self._field)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.offpeak.async_set(**{self._field: value.replace(second=0, microsecond=0)})
