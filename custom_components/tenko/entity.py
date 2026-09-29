"""Base entity for Tenko."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TenkoCoordinator


class TenkoEntity(CoordinatorEntity[TenkoCoordinator]):
    _attr_has_entity_name = True
    # True -> entity belongs to the "Tenko Heat program" sub-device
    # (off-peak / peak schedule, maintain min temperature) instead of the boiler.
    _heat_program = False

    def __init__(self, coordinator: TenkoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        data = coordinator.data or {}
        self._attr_unique_id = f"{entry_id}_{key}"
        if self._heat_program:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_heat_program")},
                name="Tenko Heat program",
                manufacturer="Tenko",
                model="Heat program",
                entry_type=DeviceEntryType.SERVICE,
                via_device=(DOMAIN, entry_id),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry_id)},
                name="Tenko",
                manufacturer="Tenko",
                model="Electric boiler",
                sw_version=data.get("VER"),
                serial_number=data.get("SN"),
            )
