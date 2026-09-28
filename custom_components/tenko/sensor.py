"""Sensors from /total_state.

Example response:
{"SN":"...","VER":"7.5w1.2","AT":"28.0","HE1":"Off","HE2":"Off","WFT":"30.9",
 "RWFT":"30.9","PMP":"On","PRS":"1.3","MMT":{"status":"Off","temp":"28.0"},
 "STAT":{"days":"25","kWt":"75"},"YSTAT":["229.202", ... 12 months],
 "BDT":{"h":"21","m":"24","dow":"5","dd":"06","mm":"04","yy":"26"},
 "ERR":{"type_total":0,"type_time":1},"POW":21,
 "MOD":{"enabled":"Off","amount":"0,6","status":"Off"},"AF":"Off","sens":"false"}
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def num(value: Any) -> float | None:
    """'1,3' / '1.3' / 1.3 -> 1.3; anything else -> None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def path(data: dict[str, Any], *keys: Any) -> Any:
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        elif isinstance(data, list) and isinstance(key, int) and key < len(data):
            data = data[key]
        else:
            return None
    return data


def _year_total(data: dict[str, Any]) -> float | None:
    values = [num(v) for v in data.get("YSTAT") or []]
    values = [v for v in values if v is not None]
    return round(sum(values), 3) if values else None


def _boiler_time(data: dict[str, Any]) -> str | None:
    b = data.get("BDT")
    if not isinstance(b, dict):
        return None
    try:
        return "20{yy}-{mm}-{dd} {h:0>2}:{m:0>2}".format(**b)
    except (KeyError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class TenkoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    raw_keys: tuple[str, ...] = ()  # top-level keys consumed by this sensor


def _temp(key: str, name: str, *keys: Any) -> TenkoSensorDescription:
    return TenkoSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: num(path(d, *keys)),
        raw_keys=(keys[0],),
    )


def _energy(key: str, name: str, fn, *, enabled: bool = True, raw=()) -> TenkoSensorDescription:
    return TenkoSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
        value_fn=fn,
        raw_keys=raw,
    )


SENSORS: tuple[TenkoSensorDescription, ...] = (
    _temp("air_temperature", "Air temperature", "AT"),
    _temp("water_feed_temperature", "Water feed temperature", "WFT"),
    _temp("return_water_temperature", "Return water temperature", "RWFT"),
    _temp("mmt_temperature", "Maintain min temp: current", "MMT", "temp"),
    TenkoSensorDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: num(d.get("PRS")),
        raw_keys=("PRS",),
    ),
    TenkoSensorDescription(
        key="rated_power",
        name="Rated power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: num(d.get("POW")),
        raw_keys=("POW",),
    ),
    # --- consumption ---
    _energy(
        "energy_month",
        "Energy this month",
        lambda d: num(path(d, "STAT", "kWt")),
        raw=("STAT",),
    ),
    TenkoSensorDescription(
        key="stat_days",
        name="Energy this month: days counted",
        icon="mdi:calendar-month",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: num(path(d, "STAT", "days")),
    ),
    _energy("energy_year", "Energy this year", _year_total, raw=("YSTAT",)),
    *(
        _energy(
            f"energy_{m}",
            f"Energy {m.capitalize()}",
            (lambda i: lambda d: num(path(d, "YSTAT", i)))(i),
            enabled=True,
        )
        for i, m in enumerate(MONTHS)
    ),
    # --- diagnostics ---
    TenkoSensorDescription(
        key="modulation_amount",
        name="Modulation amount",
        icon="mdi:tune-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: num(path(d, "MOD", "amount")),
        raw_keys=("MOD",),
    ),
    TenkoSensorDescription(
        key="errors_total",
        name="Errors total",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: num(path(d, "ERR", "type_total")),
        raw_keys=("ERR",),
    ),
    TenkoSensorDescription(
        key="errors_time",
        name="Errors time",
        icon="mdi:clock-alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: num(path(d, "ERR", "type_time")),
    ),
    TenkoSensorDescription(
        key="boiler_time",
        name="Boiler clock",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_boiler_time,
        raw_keys=("BDT",),
    ),
    TenkoSensorDescription(
        key="firmware",
        name="Firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("VER"),
        raw_keys=("VER",),
    ),
    TenkoSensorDescription(
        key="serial",
        name="Serial number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("SN"),
        raw_keys=("SN",),
    ),
)

# Keys handled elsewhere (binary_sensor.py) — not duplicated as raw sensors.
OTHER_PLATFORM_KEYS = {"HE1", "HE2", "PMP", "AF", "sens"}
KNOWN_KEYS = {k for d in SENSORS for k in d.raw_keys} | OTHER_PLATFORM_KEYS


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(TenkoSensor(coordinator, d) for d in SENSORS)

    # Any new/unknown top-level field (future firmware) appears as a raw sensor.
    known_raw: set[str] = set()

    @callback
    def _add_raw() -> None:
        new = [
            TenkoRawSensor(coordinator, key)
            for key, value in (coordinator.data or {}).items()
            if key not in KNOWN_KEYS and key not in known_raw and not isinstance(value, (dict, list))
        ]
        known_raw.update(s.raw_key for s in new)
        if new:
            async_add_entities(new)

    _add_raw()
    entry.async_on_unload(coordinator.async_add_listener(_add_raw))


class TenkoSensor(TenkoEntity, SensorEntity):
    entity_description: TenkoSensorDescription

    def __init__(self, coordinator: TenkoCoordinator, description: TenkoSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})


class TenkoRawSensor(TenkoEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TenkoCoordinator, key: str) -> None:
        super().__init__(coordinator, f"raw_{key}")
        self.raw_key = key
        self._attr_name = f"Raw {key}"

    @property
    def native_value(self) -> Any:
        value = (self.coordinator.data or {}).get(self.raw_key)
        return None if value is None else str(value)[:255]
