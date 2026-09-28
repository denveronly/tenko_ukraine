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

from . import TenkoConfigEntry
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity
from .sensor import num, path


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


class TenkoBinarySensor(TenkoEntity, BinarySensorEntity):
    entity_description: TenkoBinaryDescription

    def __init__(self, coordinator: TenkoCoordinator, description: TenkoBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data or {})
