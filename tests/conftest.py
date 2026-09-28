"""Fixtures for Tenko tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


# Real /total_state shape (serial anonymised)
TOTAL_STATE = {
    "SN": "00000000", "VER": "7.5w1.2", "AT": "28.0", "HE1": "Off", "HE2": "On",
    "WFT": "30.9", "RWFT": "30.9", "PMP": "On", "PRS": "1.3",
    "MMT": {"status": "Off", "temp": "28.0"},
    "STAT": {"days": "25", "kWt": "75"},
    "YSTAT": ["229.202", "0.0", "0.0", "1342.336", "716.420", "0.0",
              "1522.107", "45.101", "234.132", "1288.481", "149.516", "0.0"],
    "BDT": {"h": "21", "m": "24", "dow": "5", "dd": "06", "mm": "04", "yy": "26"},
    "ERR": {"type_total": 0, "type_time": 1}, "POW": 21,
    "MOD": {"enabled": "Off", "amount": "0,6", "status": "Off"},
    "AF": "Off", "sens": "false",
}
