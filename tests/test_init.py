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
