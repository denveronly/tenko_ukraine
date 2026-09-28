"""Binary sensors: heating elements, pump, modes (from /total_state)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TenkoConfigEntry
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity
from .const import OFFLINE_AFTER_MINUTES
from .sensor import boiler_datetime, num, path


def flag(value: Any) -> bool | None:
    if value is None:
        return None
    return str(value).strip().lower() in ("on", "true", "1", "yes")


@dataclass(frozen=True, kw_only=True)
class TenkoBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[TenkoBinaryDescription, ...] = (
    TenkoBinaryDescription(
        key="heater_1", name="Heating element 1", device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda d: flag(d.get("HE1")),
    ),
    TenkoBinaryDescription(
        key="heater_2", name="Heating element 2", device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda d: flag(d.get("HE2")),
    ),
    TenkoBinaryDescription(
        key="pump", name="Pump", device_class=BinarySensorDeviceClass.RUNNING, icon="mdi:pump",
        value_fn=lambda d: flag(d.get("PMP")),
    ),
    TenkoBinaryDescription(
        key="antifreeze", name="Antifreeze (AF)", icon="mdi:snowflake-alert",
        value_fn=lambda d: flag(d.get("AF")),
    ),
    TenkoBinaryDescription(
        key="modulation_enabled", name="Modulation enabled", icon="mdi:tune-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: flag(path(d, "MOD", "enabled")),
    ),
    TenkoBinaryDescription(
        key="modulation_active", name="Modulation active", icon="mdi:tune-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: flag(path(d, "MOD", "status")),
    ),
    TenkoBinaryDescription(
        key="external_sensor", name="External sensor (sens)",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: flag(d.get("sens")),
    ),
    TenkoBinaryDescription(
        key="error", name="Error", device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: None if num(path(d, "ERR", "type_total")) is None
        else num(path(d, "ERR", "type_total")) > 0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(TenkoBinarySensor(coordinator, d) for d in BINARY_SENSORS)
    async_add_entities([TenkoOffPeakSensor(coordinator), TenkoOnlineSensor(coordinator)])


class TenkoBinarySensor(TenkoEntity, BinarySensorEntity):
    entity_description: TenkoBinaryDescription

    def __init__(self, coordinator: TenkoCoordinator, description: TenkoBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data or {})


class TenkoOffPeakSensor(TenkoEntity, BinarySensorEntity):
    """On while the current time is inside the off-peak window."""

    _attr_name = "Off-peak"
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator: TenkoCoordinator) -> None:
        super().__init__(coordinator, "off_peak")

    @property
    def is_on(self) -> bool:
        return self.coordinator.offpeak.is_off_peak()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        op = self.coordinator.offpeak
        return {
            "start": op.start.strftime("%H:%M"),
            "end": op.end.strftime("%H:%M"),
            "next_change": op.next_change(),
            "peak_control": op.enabled,
            "heat_stages_at_start": op.heat_stages,
            "stages_to_restore": op.saved_stages,
        }


class TenkoOnlineSensor(TenkoEntity, BinarySensorEntity):
    """Off when the server only has old data (the boiler stopped reporting).

    The server keeps serving the last snapshot the boiler sent, so polling
    faster does not help when the boiler itself is offline.
    """

    _attr_name = "Boiler online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TenkoCoordinator) -> None:
        super().__init__(coordinator, "boiler_online")

    @property
    def is_on(self) -> bool | None:
        last = boiler_datetime(self.coordinator.data or {})
        if last is None:
            return None
        return (dt_util.now() - last).total_seconds() <= OFFLINE_AFTER_MINUTES * 60

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = boiler_datetime(self.coordinator.data or {})
        return {
            "last_data": last.isoformat() if last else None,
            "data_age_minutes": int((dt_util.now() - last).total_seconds() // 60) if last else None,
        }
