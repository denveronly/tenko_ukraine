"""Base entity for Tenko."""

from __future__ import annotations

from homeassistant.helpers.typing import UndefinedType
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_ORDER
from .coordinator import TenkoCoordinator


class TenkoEntity(CoordinatorEntity[TenkoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TenkoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        data = coordinator.data or {}
        self._tenko_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Tenko",
            manufacturer="Tenko",
            model="Electric boiler",
            sw_version=data.get("VER"),
            serial_number=data.get("SN"),
        )

    def _base_name(self) -> str | None:
        if getattr(self, "_attr_name", None):
            return self._attr_name
        description = getattr(self, "entity_description", None)
        name = getattr(description, "name", None)
        return name if isinstance(name, str) else None

    @property
    def name(self) -> str | UndefinedType | None:
        """'1. Stage 1' — the number only controls the order on the device page."""
        base = self._base_name()
        position = ENTITY_ORDER.get(self._tenko_key)
        if base and position is not None:
            return f"{position}. {base}"
        return base

    @property
    def suggested_object_id(self) -> str | None:
        """Entity ID without the order number: number.tenko_water_feed."""
        return self._base_name()
