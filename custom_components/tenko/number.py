"""Setpoints: water feed, return water feed, constant temp, min-temp window."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    NumberEntity,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .const import GROUP_COT, GROUP_MMT, GROUP_PSS, GROUP_RWF, GROUP_WF
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity


@dataclass(frozen=True, kw_only=True)
class TenkoNumberDescription(NumberEntityDescription):
    group: str
    field: str


def _temp(key, name, group, field, lo, hi, step=1.0):
    return TenkoNumberDescription(
        key=key,
        name=name,
        group=group,
        field=field,
        native_min_value=lo,
        native_max_value=hi,
        native_step=step,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
    )


NUMBERS: tuple[TenkoNumberDescription, ...] = (
    _temp("water_feed", "Water feed", GROUP_WF, "temp", 20, 85),
    _temp("water_feed_delta", "Water feed delta", GROUP_WF, "delta", 1, 10),
    _temp("returned_water_feed", "Return water feed", GROUP_RWF, "temp", 20, 85),
    _temp("returned_water_feed_delta", "Return water feed delta", GROUP_RWF, "delta", 1, 10),
    _temp("const_temp", "Constant air temperature", GROUP_COT, "temp", 5, 30, 0.5),
    _temp("min_temp_low", "Maintain min temp: min", GROUP_MMT, "min_temp", 1, 25),
    _temp("min_temp_high", "Maintain min temp: max", GROUP_MMT, "max_temp", 1, 25),
    TenkoNumberDescription(
        key="pause_1", name="Pause 1", icon="mdi:timer-pause-outline", group=GROUP_PSS, field="pause_1",
        native_min_value=0, native_max_value=60, native_step=1, mode=NumberMode.BOX,
        device_class=NumberDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    TenkoNumberDescription(
        key="pause_2", name="Pause 2", icon="mdi:timer-pause-outline", group=GROUP_PSS, field="pause_2",
        native_min_value=0, native_max_value=60, native_step=1, mode=NumberMode.BOX,
        device_class=NumberDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(TenkoNumber(coordinator, d) for d in NUMBERS)


class TenkoNumber(TenkoEntity, NumberEntity):
    entity_description: TenkoNumberDescription

    def __init__(self, coordinator: TenkoCoordinator, description: TenkoNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.commands[self.entity_description.group][self.entity_description.field]
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        d = self.entity_description
        await self.coordinator.async_send(d.group, **{d.field: _fmt(value)})


def _fmt(value: float) -> str:
    """40.0 -> "40", 40.5 -> "40.5" (API takes strings like in Node-RED)."""
    return str(int(value)) if float(value).is_integer() else str(value)
