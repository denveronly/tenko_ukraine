"""Switches: heating stages, modes, modulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .const import GROUP_COT, GROUP_MMT, GROUP_MOD, GROUP_STG, STATUS_OFF, STATUS_ON
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity


@dataclass(frozen=True, kw_only=True)
class TenkoSwitchDescription(SwitchEntityDescription):
    group: str
    field: str | None = None  # None -> the group value itself is "On"/"Off"
    heat_program: bool = False  # belongs to the 'Tenko Heat program' device


SWITCHES: tuple[TenkoSwitchDescription, ...] = (
    TenkoSwitchDescription(key="stage_1", name="Stage 1", icon="mdi:heating-coil", group=GROUP_STG, field="stage_1"),
    TenkoSwitchDescription(key="stage_2", name="Stage 2", icon="mdi:heating-coil", group=GROUP_STG, field="stage_2"),
    TenkoSwitchDescription(key="const_temp_mode", name="Constant air temperature", icon="mdi:thermostat", group=GROUP_COT, field="status"),
    TenkoSwitchDescription(key="maintain_min_temp", name="Maintain min temperature", icon="mdi:snowflake-thermometer", group=GROUP_MMT, field="status", heat_program=True),
    TenkoSwitchDescription(key="modulation", name="Modulation", icon="mdi:tune-variant", group=GROUP_MOD),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(TenkoSwitch(coordinator, d) for d in SWITCHES)
    async_add_entities(
        [
            TenkoOffPeakSwitch(coordinator, "peak_control", "Turn off stages in peak", "mdi:transmission-tower-off", "enabled"),
            TenkoOffPeakSwitch(coordinator, "restore_after_peak", "Restore stages after peak", "mdi:restore", "restore"),
            TenkoOffPeakSwitch(coordinator, "off_peak_heat_stage_1", "Off-peak heating: stage 1", "mdi:heating-coil", "heat_stage_1"),
            TenkoOffPeakSwitch(coordinator, "off_peak_heat_stage_2", "Off-peak heating: stage 2", "mdi:heating-coil", "heat_stage_2"),
        ]
    )


class TenkoSwitch(TenkoEntity, SwitchEntity):
    entity_description: TenkoSwitchDescription

    def __init__(self, coordinator: TenkoCoordinator, description: TenkoSwitchDescription) -> None:
        self._heat_program = description.heat_program
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        d = self.entity_description
        value = self.coordinator.commands[d.group]
        if d.field:
            value = value[d.field]
        return str(value).lower() == "on"

    async def _set(self, status: str) -> None:
        d = self.entity_description
        if d.field:
            await self.coordinator.async_send(d.group, **{d.field: status})
        else:
            await self.coordinator.async_send(d.group, status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        offpeak = self.coordinator.offpeak
        if self.entity_description.group == GROUP_STG and offpeak and offpeak.blocks_stage_on():
            raise HomeAssistantError(
                f"Peak time: stages are blocked until off-peak starts at {offpeak.next_change()} "
                "(disable 'Turn off stages in peak' to override)"
            )
        await self._set(STATUS_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(STATUS_OFF)


class TenkoOffPeakSwitch(TenkoEntity, SwitchEntity):
    """Settings of the off-peak control (stored in HA, not on the boiler)."""

    _heat_program = True

    def __init__(self, coordinator: TenkoCoordinator, key: str, name: str, icon: str, field: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_icon = icon
        self._field = field

    @property
    def is_on(self) -> bool:
        op = self.coordinator.offpeak
        if self._field.startswith("heat_stage_"):
            return self._field.removeprefix("heat_") in op.heat_stages
        return bool(getattr(op, self._field))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.offpeak.async_set(**{self._field: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.offpeak.async_set(**{self._field: False})
