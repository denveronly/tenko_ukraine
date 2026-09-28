"""Constants for the Tenko boiler integration."""

from datetime import timedelta

DOMAIN = "tenko"

CONF_LOGIN = "login"
CONF_TOKEN = "token"

DEFAULT_HOST = "http://188.166.117.80"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

API_PREFIX = "/api/v1"

# Endpoints (same as in the original Node-RED flow)
EP_AUTH = "/auth"
EP_TOTAL_STATE = "/total_state"
EP_WATER_FEED = "/water_feed"  # {"WF": {"temp", "delta"}}
EP_RETURNED_WATER_FEED = "/returned_water_feed"  # {"RWF": {"temp", "delta"}}
EP_CONST_TEMP = "/const_temp"  # {"COT": {"status", "temp"}}
EP_MAINTAIN_MIN_TEMP = "/maintain_min_temp"  # {"MMT": {"status", "min_temp", "max_temp"}}
EP_STAGES = "/stages"  # {"STG": {"stage_1", "stage_2"}}

# Command groups: every POST must carry all fields of its group,
# so the coordinator keeps the last known value of each field.
GROUP_WF = "WF"
GROUP_RWF = "RWF"
GROUP_COT = "COT"
GROUP_MMT = "MMT"
GROUP_STG = "STG"

GROUP_ENDPOINT = {
    GROUP_WF: EP_WATER_FEED,
    GROUP_RWF: EP_RETURNED_WATER_FEED,
    GROUP_COT: EP_CONST_TEMP,
    GROUP_MMT: EP_MAINTAIN_MIN_TEMP,
    GROUP_STG: EP_STAGES,
}

# Defaults used until the real value is known from total_state or restore
GROUP_DEFAULTS: dict[str, dict[str, str]] = {
    GROUP_WF: {"temp": "50", "delta": "2"},
    GROUP_RWF: {"temp": "40", "delta": "2"},
    GROUP_COT: {"status": "Off", "temp": "20"},
    GROUP_MMT: {"status": "Off", "min_temp": "6", "max_temp": "10"},
    GROUP_STG: {"stage_1": "Off", "stage_2": "Off"},
}

STATUS_ON = "On"
STATUS_OFF = "Off"
