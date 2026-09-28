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
    RestoreSensor,
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
from homeassistant.util import dt as dt_util

from . import TenkoConfigEntry
from .const import (
    CONF_STAGE1_POWER,
    CONF_STAGE2_POWER,
    DEFAULT_STAGE1_POWER,
    DEFAULT_STAGE2_POWER,
)
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity

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
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
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
    # --- consumption reported by the boiler ---
    # STAT = kWh over the last `days` days (rolling window, not a counter)
    TenkoSensorDescription(
        key="energy_period",
        name="Energy last N days",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda d: num(path(d, "STAT", "kWt")),
        attrs_fn=lambda d: {"days": num(path(d, "STAT", "days"))},
        raw_keys=("STAT",),
    ),
    # YSTAT = rolling 12-month history (order shifts every month, no month labels)
    TenkoSensorDescription(
        key="energy_12_months",
        name="Energy last 12 months",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=_year_total,
        attrs_fn=lambda d: {"months": [num(v) for v in d.get("YSTAT") or []]},
        raw_keys=("YSTAT",),
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
    async_add_entities(
        [
            TenkoPowerSensor(coordinator),
            TenkoEnergySensor(coordinator, daily=False),
            TenkoEnergySensor(coordinator, daily=True),
        ]
    )

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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data or {}) if fn else None


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


# --- Estimated consumption -------------------------------------------------
# The boiler has no daily counter (DSTAT exists only on "smart" boilers), so
# consumption is integrated here from which heating elements are on (HE1/HE2)
# and their power (configurable in the integration options).

MAX_GAP_SECONDS = 600  # don't integrate over outages / HA restarts


def estimated_power(coordinator: TenkoCoordinator) -> float | None:
    data = coordinator.data or {}
    he1, he2 = data.get("HE1"), data.get("HE2")
    if he1 is None and he2 is None:
        return None
    opts = coordinator.config_entry.options
    p1 = opts.get(CONF_STAGE1_POWER, DEFAULT_STAGE1_POWER)
    p2 = opts.get(CONF_STAGE2_POWER, DEFAULT_STAGE2_POWER)
    on = lambda v: str(v).lower() == "on"  # noqa: E731
    return p1 * on(he1) + p2 * on(he2)


class TenkoPowerSensor(TenkoEntity, SensorEntity):
    _attr_name = "Estimated power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TenkoCoordinator) -> None:
        super().__init__(coordinator, "estimated_power")

    @property
    def native_value(self) -> float | None:
        return estimated_power(self.coordinator)


class TenkoEnergySensor(TenkoEntity, RestoreSensor):
    """kWh integrated from estimated power; daily=True resets at local midnight."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: TenkoCoordinator, *, daily: bool) -> None:
        super().__init__(coordinator, "energy_today" if daily else "energy_total")
        self._daily = daily
        self._attr_name = "Energy today" if daily else "Energy total"
        self._energy = 0.0
        self._day = dt_util.now().date()
        self._last_time = None
        self._last_power: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None and last_state is not None:
            same_day = dt_util.as_local(last_state.last_changed).date() == self._day
            if not self._daily or same_day:
                self._energy = float(last.native_value)
        self._take_sample()

    def _take_sample(self) -> None:
        now = dt_util.utcnow()
        power = estimated_power(self.coordinator) if self.coordinator.last_update_success else None
        if self._last_time is not None and self._last_power is not None:
            seconds = (now - self._last_time).total_seconds()
            if 0 < seconds <= MAX_GAP_SECONDS:
                self._energy += self._last_power * seconds / 3600
        if self._daily and dt_util.now().date() != self._day:
            self._day = dt_util.now().date()
            self._energy = 0.0
        self._last_time, self._last_power = now, power

    @callback
    def _handle_coordinator_update(self) -> None:
        self._take_sample()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        return round(self._energy, 3)
