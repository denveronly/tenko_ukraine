"""Constants for the Tenko boiler integration."""

from datetime import timedelta

DOMAIN = "tenko"

CONF_LOGIN = "login"
CONF_TOKEN = "token"

DEFAULT_HOST = "https://my.tenko.ua"  # same server as 188.166.117.80, but HTTPS
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

API_PREFIX = "/api/v1"

# Endpoints (same as in the original Node-RED flow)
EP_AUTH = "/auth"
EP_TOTAL_STATE = "/total_state"
EP_SETTINGS = "/settings"  # GET: MMT, WF, RWF, STG, PSS, MOD
EP_USED_CHART = "/used_chart_type"  # {"USE": "Temp" | "WChart" | "DChart"}
EP_PAUSES = "/pauses"  # {"PSS": {"pause_1", "pause_2"}}
EP_MODULATION = "/modulation"  # {"MOD": "On" | "Off"}
EP_WATER_FEED = "/water_feed"  # {"WF": {"temp", "delta"}}
EP_RETURNED_WATER_FEED = "/returned_water_feed"  # {"RWF": {"temp", "delta"}}
EP_CONST_TEMP = "/const_temp"  # GET/POST {"COT": {"status", "temp"}}
EP_MAINTAIN_MIN_TEMP = "/maintain_min_temp"  # {"MMT": {"status", "min_temp", "max_temp"}}
EP_STAGES = "/stages"  # {"STG": {"stage_1", "stage_2"}}

# Command groups: every POST must carry all fields of its group,
# so the coordinator keeps the last known value of each field.
GROUP_WF = "WF"
GROUP_RWF = "RWF"
GROUP_COT = "COT"
GROUP_MMT = "MMT"
GROUP_STG = "STG"
GROUP_PSS = "PSS"
GROUP_MOD = "MOD"  # plain string value
GROUP_USE = "USE"  # plain string value

GROUP_ENDPOINT = {
    GROUP_WF: EP_WATER_FEED,
    GROUP_RWF: EP_RETURNED_WATER_FEED,
    GROUP_COT: EP_CONST_TEMP,
    GROUP_MMT: EP_MAINTAIN_MIN_TEMP,
    GROUP_STG: EP_STAGES,
    GROUP_PSS: EP_PAUSES,
    GROUP_MOD: EP_MODULATION,
    GROUP_USE: EP_USED_CHART,
}

# Placeholders until the first read of /settings, /const_temp, /used_chart_type
GROUP_DEFAULTS: dict[str, dict[str, str] | str] = {
    GROUP_WF: {"temp": "50", "delta": "2"},
    GROUP_RWF: {"temp": "40", "delta": "2"},
    GROUP_COT: {"status": "Off", "temp": "20"},
    GROUP_MMT: {"status": "Off", "min_temp": "6", "max_temp": "10"},
    GROUP_STG: {"stage_1": "Off", "stage_2": "Off"},
    GROUP_PSS: {"pause_1": "5", "pause_2": "10"},
    GROUP_MOD: "Off",
    GROUP_USE: "Temp",
}

CHART_TYPES = ("Temp", "WChart", "DChart")

# Options: element power for the energy estimate (kW)
CONF_STAGE1_POWER = "stage1_power"
CONF_STAGE2_POWER = "stage2_power"
DEFAULT_STAGE1_POWER = 7.0
DEFAULT_STAGE2_POWER = 14.0

STATUS_ON = "On"
STATUS_OFF = "Off"

# Update interval (options), seconds
CONF_SCAN_INTERVAL = "scan_interval"
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

# The boiler is considered offline if its last data (BDT clock) is older than this
OFFLINE_AFTER_MINUTES = 10

MONTH_KEYS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)

# Display order on the device page. HA sorts entities alphabetically (numbers
# numerically) inside each group, so the position is put in front of the name:
# "1. Stage 1". Entity IDs are generated without it (number.tenko_water_feed).
ENTITY_ORDER: dict[str, int] = {
    # Controls
    "stage_1": 1,
    "stage_2": 2,
    "modulation": 3,
    "water_feed": 4,
    "water_feed_delta": 5,
    "returned_water_feed": 6,
    "returned_water_feed_delta": 7,
    "pause_1": 8,
    "pause_2": 9,
    "min_temp_low": 10,
    "min_temp_high": 11,
    "maintain_min_temp": 12,
    "const_temp_mode": 13,
    "const_temp": 14,
    "used_chart_type": 15,
    "refresh": 16,
    # Sensors (sensor + binary_sensor share one group), energy last
    "water_feed_temperature": 1,
    "return_water_temperature": 2,
    "air_temperature": 3,
    "pressure": 4,
    "mmt_temperature": 5,
    "boiler_online": 6,
    "last_update": 7,
    "heater_1": 8,
    "heater_2": 9,
    "pump": 10,
    "antifreeze": 11,
    "error": 12,
    "off_peak": 13,
    "estimated_power": 14,
    "energy_today": 20,
    "energy_this_month": 21,
    "energy_previous_month": 22,
    "energy_total": 23,
    "energy_period": 24,
    "energy_12_months": 25,
    **{f"energy_{m}": 26 + i for i, m in enumerate(MONTH_KEYS)},
    # Configuration (off-peak)
    "off_peak_start": 1,
    "off_peak_end": 2,
    "peak_control": 3,
    "restore_after_peak": 4,
    "off_peak_heat_stage_1": 5,
    "off_peak_heat_stage_2": 6,
}
