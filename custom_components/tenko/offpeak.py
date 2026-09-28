"""Off-peak tariff control.

Outside the off-peak window (e.g. 23:00-07:00) the heating stages are
switched off if "Turn off stages in peak" is enabled. Stages that were
switched off this way are switched back on when the off-peak window starts
(if "Restore stages after peak" is enabled).

Settings live in HA storage (not on the boiler), so they survive restarts.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
import logging
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, GROUP_STG, STATUS_OFF, STATUS_ON
from .coordinator import TenkoCoordinator

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STAGES = ("stage_1", "stage_2")

DEFAULTS: dict[str, Any] = {
    "start": "23:00",
    "end": "07:00",
    "enabled": False,
    "restore": True,
    "saved_stages": [],  # stages we switched off at peak start
}


def in_window(now: time, start: time, end: time) -> bool:
    """True if `now` is inside [start, end); handles windows over midnight."""
    if start == end:
        return True  # whole day is off-peak
    if start < end:
        return start <= now < end
    return now >= start or now < end


class OffPeakManager:
    def __init__(self, hass: HomeAssistant, coordinator: TenkoCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{coordinator.config_entry.entry_id}.offpeak"
        )
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._unsub: CALLBACK_TYPE | None = None
        self._busy = False
        self.now: Callable[[], datetime] = dt_util.now

    # --- lifecycle -------------------------------------------------------

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data.update(stored)

    @callback
    def async_start(self) -> None:
        # Check every minute (second=5 so the minute boundary has passed)
        self._unsub = async_track_time_change(self.hass, self._on_tick, second=5)

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def _on_tick(self, _now: datetime) -> None:
        await self.async_check()

    # --- settings --------------------------------------------------------

    @property
    def start(self) -> time:
        return time.fromisoformat(self._data["start"])

    @property
    def end(self) -> time:
        return time.fromisoformat(self._data["end"])

    @property
    def enabled(self) -> bool:
        return bool(self._data["enabled"])

    @property
    def restore(self) -> bool:
        return bool(self._data["restore"])

    @property
    def saved_stages(self) -> list[str]:
        return list(self._data["saved_stages"])

    def is_off_peak(self) -> bool:
        return in_window(self.now().time(), self.start, self.end)

    def next_change(self) -> str:
        return (self.end if self.is_off_peak() else self.start).strftime("%H:%M")

    async def async_set(self, **changes: Any) -> None:
        for key, value in changes.items():
            self._data[key] = value.strftime("%H:%M") if isinstance(value, time) else value
        await self._store.async_save(self._data)
        self.coordinator.async_update_listeners()
        await self.async_check()

    # --- control ---------------------------------------------------------

    def blocks_stage_on(self) -> bool:
        """Manual 'stage on' is refused during peak while control is enabled."""
        return self.enabled and not self.is_off_peak()

    async def async_check(self) -> None:
        if not self.enabled or self._busy or not self.coordinator.last_update_success:
            self.coordinator.async_update_listeners()
            return
        self._busy = True
        try:
            stg = self.coordinator.commands[GROUP_STG]
            on_now = [s for s in STAGES if str(stg.get(s)).lower() == "on"]

            if not self.is_off_peak():
                if on_now:
                    _LOGGER.info("Peak time: switching off %s", ", ".join(on_now))
                    await self.coordinator.async_send(
                        GROUP_STG, **{s: STATUS_OFF for s in STAGES}
                    )
                    saved = sorted(set(self.saved_stages) | set(on_now))
                    self._data["saved_stages"] = saved
                    await self._store.async_save(self._data)
            elif self.saved_stages:
                if self.restore:
                    _LOGGER.info("Off-peak started: restoring %s", ", ".join(self.saved_stages))
                    await self.coordinator.async_send(
                        GROUP_STG, **{s: STATUS_ON for s in self.saved_stages}
                    )
                self._data["saved_stages"] = []
                await self._store.async_save(self._data)
        except HomeAssistantError as err:
            _LOGGER.warning("Off-peak control failed: %s", err)
        finally:
            self._busy = False
            self.coordinator.async_update_listeners()
