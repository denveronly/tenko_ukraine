"""End-to-end tests with a mocked Tenko server."""

import json

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tenko.const import DOMAIN

from .conftest import TOTAL_STATE

HOST = "http://tenko.test"
URL = HOST + "/api/v1"


async def _setup(hass, aioclient_mock):
    aioclient_mock.get(URL + "/total_state", json=TOTAL_STATE)
    entry = MockConfigEntry(domain=DOMAIN, data={"host": HOST, "token": "t0k"}, unique_id="00000000")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_login(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL + "/auth", text=json.dumps({"token": "fresh"}))
    aioclient_mock.get(URL + "/total_state", json=TOTAL_STATE)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "login": "u", "password": "p", "token": ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": HOST, "login": "u", "password": "p"}
    # token obtained via /auth was used for total_state
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "Bearer fresh"


async def test_config_flow_missing_credentials(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": HOST})
    assert result["errors"] == {"base": "missing_credentials"}


async def test_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    s = hass.states.get
    assert s("sensor.tenko_air_temperature").state == "28.0"
    assert s("sensor.tenko_water_feed_temperature").state == "30.9"
    assert s("sensor.tenko_pressure").state == "1.3"
    assert s("sensor.tenko_energy_this_month").state == "75.0"
    assert float(s("sensor.tenko_energy_this_year").state) == 5527.295
    assert s("sensor.tenko_energy_apr").state == "1342.336"
    assert s("sensor.tenko_modulation_amount").state == "0.6"
    assert s("binary_sensor.tenko_heating_element_2").state == "on"
    assert s("binary_sensor.tenko_heating_element_1").state == "off"
    assert s("binary_sensor.tenko_pump").state == "on"
    assert s("binary_sensor.tenko_error").state == "off"


async def test_commands(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    aioclient_mock.post(URL + "/water_feed", json={})
    aioclient_mock.post(URL + "/stages", json={})

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.tenko_water_feed", "value": 55}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.tenko_stage_2"}, blocking=True
    )
    posts = [(str(c[1]), c[2]) for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts == [
        (URL + "/water_feed", {"WF": {"temp": "55", "delta": "2"}}),
        (URL + "/stages", {"STG": {"stage_1": "Off", "stage_2": "On"}}),
    ]
    assert hass.states.get("number.tenko_water_feed").state == "55.0"
    assert hass.states.get("switch.tenko_stage_2").state == "on"
