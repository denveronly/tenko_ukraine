"""End-to-end tests with a mocked Tenko server."""

import json
from datetime import timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.tenko.const import DOMAIN

from .conftest import CONST_TEMP, SETTINGS, TOTAL_STATE, USED_CHART

HOST = "https://tenko.test"
URL = HOST + "/api/v1"


def _mock_reads(aioclient_mock, state=TOTAL_STATE, status=200):
    aioclient_mock.get(URL + "/total_state", json=state, status=status)
    aioclient_mock.get(URL + "/settings", json=SETTINGS)
    aioclient_mock.get(URL + "/const_temp", json=CONST_TEMP)
    aioclient_mock.get(URL + "/used_chart_type", json=USED_CHART)


async def _setup(hass, aioclient_mock, options=None):
    _mock_reads(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": HOST, "login": "u", "token": "stored-token"},
        options=options or {},
        unique_id="00000000",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_gets_and_stores_token(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL + "/auth", text=json.dumps({"status": "ok", "token": "fresh"}))
    _mock_reads(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "login": "u", "password": "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # token stored, password NOT stored
    assert result["data"] == {"host": HOST, "login": "u", "token": "fresh"}
    assert result["result"].unique_id == "00000000"
    # /auth got login+password as form data; later calls use the token
    auth_call = next(c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/auth"))
    assert auth_call[2] == {"login": "u", "password": "secret"}
    assert all(
        c[3]["Authorization"] == "Bearer fresh"
        for c in aioclient_mock.mock_calls
        if not str(c[1]).endswith("/auth")
    )


async def test_config_flow_bad_password(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL + "/auth", status=401, text=json.dumps({"status": "error", "message": "bad"}))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "login": "u", "password": "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_rejected_token_starts_reauth(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_reads(aioclient_mock, status=401)
    entry = MockConfigEntry(domain=DOMAIN, data={"host": HOST, "login": "u", "token": "old"}, unique_id="00000000")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]

    aioclient_mock.clear_requests()
    aioclient_mock.post(URL + "/auth", text=json.dumps({"token": "new"}))
    _mock_reads(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"login": "u", "password": "secret"}
    )
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"host": HOST, "login": "u", "token": "new"}


async def test_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    s = hass.states.get
    assert s("sensor.tenko_air_temperature").state == "28.0"
    assert s("sensor.tenko_water_feed_temperature").state == "30.9"
    assert s("sensor.tenko_pressure").state == "1.3"
    assert s("sensor.tenko_energy_last_n_days").state == "75.0"
    assert s("sensor.tenko_energy_last_n_days").attributes["days"] == 25
    assert float(s("sensor.tenko_energy_last_12_months").state) == 5527.295
    assert s("sensor.tenko_modulation_amount").state == "0.6"
    assert s("binary_sensor.tenko_heating_element_2").state == "on"
    assert s("binary_sensor.tenko_heating_element_1").state == "off"
    assert s("binary_sensor.tenko_pump").state == "on"
    assert s("binary_sensor.tenko_error").state == "off"


async def test_real_setpoints(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    s = hass.states.get
    assert s("number.tenko_water_feed").state == "30.0"
    assert s("number.tenko_return_water_feed").state == "24.0"
    assert s("number.tenko_constant_air_temperature").state == "29.5"
    assert s("number.tenko_pause_2").state == "10.0"
    assert s("switch.tenko_constant_air_temperature").state == "on"
    assert s("switch.tenko_modulation").state == "off"
    assert s("select.tenko_program").state == "Temp"


async def test_commands(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    for ep in ("water_feed", "stages", "modulation", "used_chart_type"):
        aioclient_mock.post(URL + "/" + ep, json={"status": "ok"})

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.tenko_water_feed", "value": 55}, blocking=True
    )
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tenko_stage_2"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tenko_modulation"}, blocking=True)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.tenko_program", "option": "WChart"}, blocking=True
    )
    posts = [(str(c[1]), c[2]) for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts == [
        (URL + "/water_feed", {"WF": {"temp": "55", "delta": "3"}}),
        (URL + "/stages", {"STG": {"stage_1": "Off", "stage_2": "On"}}),
        (URL + "/modulation", {"MOD": "On"}),
        (URL + "/used_chart_type", {"USE": "WChart"}),
    ]
    assert hass.states.get("number.tenko_water_feed").state == "55.0"


async def test_energy_estimate(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    await _setup(hass, aioclient_mock)  # HE2 on -> 14 kW by default
    assert hass.states.get("sensor.tenko_estimated_power").state == "14.0"
    # one poll later (60 s) -> 14 kW * 1/60 h = 0.233 kWh
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    today = float(hass.states.get("sensor.tenko_energy_today").state)
    total = float(hass.states.get("sensor.tenko_energy_total").state)
    assert 0.2 < today < 0.3
    assert today == total


async def test_monthly_energy(hass: HomeAssistant, aioclient_mock) -> None:
    # fixture: boiler clock = April 2026, YSTAT oldest (May 2025) -> newest (Apr 2026)
    await _setup(hass, aioclient_mock)
    s = hass.states.get
    assert s("sensor.tenko_energy_this_month").state == "0.0"  # April
    assert s("sensor.tenko_energy_previous_month").state == "149.516"  # March
    assert s("sensor.tenko_energy_may").state == "229.202"
    assert s("sensor.tenko_energy_may").attributes["year"] == 2025
    assert s("sensor.tenko_energy_november").state == "1522.107"
    assert s("sensor.tenko_energy_january").state == "234.132"
    assert s("sensor.tenko_energy_january").attributes["year"] == 2026
    months = s("sensor.tenko_energy_last_12_months").attributes
    assert list(months)[:2] == ["2025-05", "2025-06"] and months["2026-04"] == 0.0


def test_in_window() -> None:
    from datetime import time as t

    from custom_components.tenko.offpeak import in_window

    assert in_window(t(23, 30), t(23), t(7))
    assert in_window(t(6, 59), t(23), t(7))
    assert not in_window(t(7, 0), t(23), t(7))
    assert not in_window(t(12), t(23), t(7))
    assert in_window(t(12), t(10), t(14)) and not in_window(t(15), t(10), t(14))


async def test_peak_control(hass: HomeAssistant, aioclient_mock) -> None:
    from datetime import datetime

    from homeassistant.exceptions import HomeAssistantError
    import pytest

    entry = await _setup(hass, aioclient_mock)
    aioclient_mock.post(URL + "/stages", json={"status": "ok"})
    op = entry.runtime_data.offpeak
    clock = {"now": datetime(2026, 9, 28, 23, 30)}
    op.now = lambda: clock["now"]

    s = hass.states.get
    assert s("time.tenko_heat_program_off_peak_start").state == "23:00:00"
    assert s("time.tenko_heat_program_off_peak_end").state == "07:00:00"

    # off-peak night: stage 2 on, control enabled
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tenko_stage_2"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tenko_heat_program_turn_off_stages_in_peak"}, blocking=True)
    assert s("binary_sensor.tenko_heat_program_off_peak").state == "on"
    assert s("switch.tenko_stage_2").state == "on"

    # 07:01 -> peak: stages switched off and remembered
    clock["now"] = datetime(2026, 9, 29, 7, 1)
    await op.async_check()
    await hass.async_block_till_done()
    assert s("switch.tenko_stage_2").state == "off"
    assert s("binary_sensor.tenko_heat_program_off_peak").state == "off"
    assert s("binary_sensor.tenko_heat_program_off_peak").attributes["stages_to_restore"] == ["stage_2"]

    # manual turn on during peak is refused
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tenko_stage_1"}, blocking=True)

    # move off-peak start to 22:00 via the time entity, then 22:00 -> restored
    await hass.services.async_call(
        "time", "set_value", {"entity_id": "time.tenko_heat_program_off_peak_start", "time": "22:00:00"}, blocking=True
    )
    clock["now"] = datetime(2026, 9, 29, 22, 0, 5)
    await op.async_check()
    await hass.async_block_till_done()
    assert s("switch.tenko_stage_2").state == "on"
    assert s("switch.tenko_stage_1").state == "off"

    posts = [c[2] for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts == [
        {"STG": {"stage_1": "Off", "stage_2": "On"}},   # manual, night
        {"STG": {"stage_1": "Off", "stage_2": "Off"}},  # peak shutdown
        {"STG": {"stage_1": "Off", "stage_2": "On"}},   # restore at off-peak start
    ]


async def test_temperature_sliders(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    for entity in (
        "number.tenko_water_feed",
        "number.tenko_return_water_feed",
        "number.tenko_water_feed_delta",
        "number.tenko_constant_air_temperature",
        "number.tenko_maintain_min_temp_min",
    ):
        assert hass.states.get(entity).attributes["mode"] == "slider", entity
    pause = hass.states.get("number.tenko_pause_1")
    assert pause.attributes["mode"] == "box"
    assert pause.attributes["unit_of_measurement"] == "min"
    assert pause.attributes["device_class"] == "duration"
    assert hass.states.get("number.tenko_constant_air_temperature").attributes["step"] == 0.5

    aioclient_mock.post(URL + "/const_temp", json={"status": "ok"})
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.tenko_constant_air_temperature", "value": 21.5}, blocking=True
    )
    post = [c[2] for c in aioclient_mock.mock_calls if c[0] == "POST"][-1]
    assert post == {"COT": {"status": "On", "temp": "21.5"}}


async def test_entity_order_and_ids(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    name = lambda e: hass.states.get(e).attributes["friendly_name"]  # noqa: E731
    # IDs have no numbers, names do (HA sorts the device page by name)
    assert name("switch.tenko_stage_1") == "Tenko 1. Stage 1"
    assert name("switch.tenko_modulation") == "Tenko 3. Modulation"
    assert name("number.tenko_water_feed") == "Tenko 4. Water feed"
    assert name("number.tenko_pause_2") == "Tenko 9. Pause 2"
    assert name("number.tenko_maintain_min_temp_max") == "Tenko 11. Maintain min temp: max"
    assert name("sensor.tenko_water_feed_temperature") == "Tenko 1. Water feed temperature"
    assert name("sensor.tenko_return_water_temperature") == "Tenko 2. Return water temperature"
    assert name("sensor.tenko_energy_december") == "Tenko 37. Energy December"
    # sorted like the HA device page does (numeric collation) -> energy last
    import re

    sensors = sorted(
        (s.attributes["friendly_name"] for s in hass.states.async_all(("sensor", "binary_sensor"))
         if s.attributes["friendly_name"].split()[1][0].isdigit()),
        key=lambda n: int(re.match(r"Tenko (\d+)\.", n).group(1)),
    )
    assert sensors[0].endswith("Water feed temperature")
    assert all("Energy" in n for n in sensors[-18:])


async def test_boiler_online(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    # fixture BDT = 2026-04-06 21:24 local
    freezer.move_to("2026-04-06 21:30:00+03:00")
    await hass.config.async_set_time_zone("Europe/Kyiv")
    await _setup(hass, aioclient_mock)
    online = hass.states.get("binary_sensor.tenko_boiler_online")
    assert online.state == "on" and online.attributes["data_age_minutes"] == 6
    assert hass.states.get("sensor.tenko_last_data_from_boiler").state == "2026-04-06T18:24:00+00:00"

    freezer.move_to("2026-04-06 22:00:00+03:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.tenko_boiler_online").state == "off"


async def test_scan_interval_option_and_refresh(hass: HomeAssistant, aioclient_mock) -> None:
    entry = await _setup(hass, aioclient_mock, options={"scan_interval": 15})
    assert entry.runtime_data.update_interval == timedelta(seconds=15)
    calls = aioclient_mock.call_count
    await hass.services.async_call("button", "press", {"entity_id": "button.tenko_refresh"}, blocking=True)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == calls + 4  # total_state, settings, const_temp, used_chart_type


async def test_off_peak_start_heating(hass: HomeAssistant, aioclient_mock) -> None:
    from datetime import datetime

    entry = await _setup(hass, aioclient_mock)
    aioclient_mock.post(URL + "/stages", json={"status": "ok"})
    op = entry.runtime_data.offpeak
    clock = {"now": datetime(2026, 9, 29, 12, 0)}
    op.now = lambda: clock["now"]

    # daytime: choose stage 1 for off-peak heating -> nothing happens yet
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.tenko_heat_program_off_peak_heating_stage_1"}, blocking=True
    )
    assert hass.states.get("switch.tenko_stage_1").state == "off"

    # 23:00 -> stage 1 on, once
    clock["now"] = datetime(2026, 9, 29, 23, 0, 5)
    await op.async_check()
    await op.async_check()
    assert hass.states.get("switch.tenko_stage_1").state == "on"
    posts = [c[2] for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts == [{"STG": {"stage_1": "On", "stage_2": "Off"}}]

    # choosing stage 2 in the middle of the night applies immediately
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.tenko_heat_program_off_peak_heating_stage_2"}, blocking=True
    )
    assert hass.states.get("switch.tenko_stage_2").state == "on"


async def test_options_flow(hass: HomeAssistant, aioclient_mock) -> None:
    entry = await _setup(hass, aioclient_mock)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, "stage1_power": 7, "stage2_power": 14}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()  # entry reloads with the new interval
    assert entry.runtime_data.update_interval == timedelta(seconds=30)


async def test_heat_program_device(hass: HomeAssistant, aioclient_mock) -> None:
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    entry = await _setup(hass, aioclient_mock)
    devices = {d.name: d for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)}
    assert set(devices) == {"Tenko", "Tenko Heat program"}
    program = devices["Tenko Heat program"]
    assert program.via_device_id == devices["Tenko"].id

    ents = er.async_entries_for_device(er.async_get(hass), program.id)
    assert sorted(e.entity_id for e in ents) == [
        "binary_sensor.tenko_heat_program_off_peak",
        "switch.tenko_heat_program_off_peak_heating_stage_1",
        "switch.tenko_heat_program_off_peak_heating_stage_2",
        "switch.tenko_heat_program_restore_stages_after_peak",
        "switch.tenko_heat_program_turn_off_stages_in_peak",
        "time.tenko_heat_program_off_peak_end",
        "time.tenko_heat_program_off_peak_start",
    ]
    assert all(e.entity_category is None for e in ents)  # shown as controls, not "Configuration"
    assert hass.states.get("time.tenko_heat_program_off_peak_start").attributes["friendly_name"] == (
        "Tenko Heat program 1. Off-peak start"
    )


async def test_existing_install_keeps_ids(hass: HomeAssistant, aioclient_mock) -> None:
    """Entities registered by an older version keep their IDs and move to Heat program."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    _mock_reads(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data={"host": HOST, "login": "u", "token": "t"}, unique_id="00000000")
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    old = ent_reg.async_get_or_create(
        "time", DOMAIN, f"{entry.entry_id}_off_peak_start",
        config_entry=entry, suggested_object_id="tenko_off_peak_start",
    )
    assert old.entity_id == "time.tenko_off_peak_start"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    moved = ent_reg.async_get("time.tenko_off_peak_start")
    assert dr.async_get(hass).async_get(moved.device_id).name == "Tenko Heat program"
    assert hass.states.get("time.tenko_off_peak_start").state == "23:00:00"
