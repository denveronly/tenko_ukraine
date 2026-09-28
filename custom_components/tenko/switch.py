"""Switches: heating stages, modes, modulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TenkoConfigEntry
from .const import GROUP_COT, GROUP_MMT, GROUP_MOD, GROUP_STG, STATUS_OFF, STATUS_ON
from .coordinator import TenkoCoordinator
from .entity import TenkoEntity


@dataclass(frozen=True, kw_only=True)
class TenkoSwitchDescription(SwitchEntityDescription):
    group: str
    field: str | None = None  # None -> the group value itself is "On"/"Off"


SWITCHES: tuple[TenkoSwitchDescription, ...] = (
    TenkoSwitchDescription(key="stage_1", name="Stage 1", icon="mdi:heating-coil", group=GROUP_STG, field="stage_1"),
    TenkoSwitchDescription(key="stage_2", name="Stage 2", icon="mdi:heating-coil", group=GROUP_STG, field="stage_2"),
    TenkoSwitchDescription(key="const_temp_mode", name="Constant air temperature", icon="mdi:thermostat", group=GROUP_COT, field="status"),
    TenkoSwitchDescription(key="maintain_min_temp", name="Maintain min temperature", icon="mdi:snowflake-thermometer", group=GROUP_MMT, field="status"),
    TenkoSwitchDescription(key="modulation", name="Modulation", icon="mdi:tune-variant", group=GROUP_MOD),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TenkoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(TenkoSwitch(coordinator, d) for d in SWITCHES)


class TenkoSwitch(TenkoEntity, SwitchEntity):
    entity_description: TenkoSwitchDescription

    def __init__(self, coordinator: TenkoCoordinator, description: TenkoSwitchDescription) -> None:
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
        await self._set(STATUS_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(STATUS_OFF)
