# Tenko Boiler — Home Assistant integration

A custom integration for the **Tenko** electric boiler that talks to its cloud API (`/api/v1`). It replaces the Node-RED flow: no MQTT, no `input_number`/`input_boolean`.

## Installation

**HACS:** HACS → ⋮ → Custom repositories → the URL of this repo, category *Integration* → install → restart HA.

**Manually:** copy `custom_components/tenko` into `/config/custom_components/` and restart HA.

Then go to *Settings → Devices & Services → Add Integration → Tenko Boiler* and enter:
- **Server URL**: `http://188.166.117.80` by default
- **Login + password**: the token is fetched automatically and refreshed on a 401, **or**
- **API token**: an existing Bearer token

> 🔐 The login, password and token are stored only in HA's `.storage` (config entry). They are not in the repository and must not be.

## Entities

| Type | Entity | API source |
|---|---|---|
| sensor | Air temperature | `AT` |
| sensor | Water feed / return water temperature | `WFT`, `RWFT` |
| sensor | Pressure (bar) | `PRS` |
| sensor | Energy this month (kWh) | `STAT.kWt` |
| sensor | Energy this year (kWh, sum of months) | `YSTAT` |
| sensor | Energy Jan…Dec (kWh) | `YSTAT[0..11]` |
| sensor | Rated power, modulation, errors, boiler clock, firmware, serial number | `POW`, `MOD`, `ERR`, `BDT`, `VER`, `SN` |
| binary_sensor | Heating element 1 / 2 (actually heating) | `HE1`, `HE2` |
| binary_sensor | Pump, antifreeze, error, modulation | `PMP`, `AF`, `ERR`, `MOD` |
| number | Water feed + delta | POST `/water_feed` `{"WF":{temp,delta}}` |
| number | Return water feed + delta | POST `/returned_water_feed` `{"RWF":{…}}` |
| number | Constant air temperature | POST `/const_temp` `{"COT":{…}}` |
| number | Maintain min temp: min / max | POST `/maintain_min_temp` `{"MMT":{…}}` |
| switch | Stage 1 / Stage 2 | POST `/stages` `{"STG":{stage_1,stage_2}}` |
| switch | Constant air temperature / Maintain min temperature | `COT.status`, `MMT.status` |

Fields the API does not return (WF/RWF/COT/STG setpoints) are remembered by HA and restored after a restart. When you change one value, its whole group is sent (for example temp+delta), just like in Node-RED. Any new field from future firmware appears automatically as a `Raw …` diagnostic sensor.

## Daily consumption

The API returns only monthly and yearly consumption. The daily value comes from the monthly counter using `utility_meter`:

```yaml
utility_meter:
  tenko_energy_daily:
    name: Tenko energy today
    source: sensor.tenko_energy_this_month
    cycle: daily
```

`sensor.tenko_energy_this_month` can also be added directly to the **Energy dashboard** (`total_increasing`, kWh).

## Weather-compensated control

Your old Node-RED logic (outdoor temperature → water feed) is now a regular automation over `number.tenko_water_feed` / `number.tenko_returned_water_feed` and `switch.tenko_stage_1/2`.

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```

Before committing, `scripts/check-secrets.sh` checks that no JWT/Bearer token got into the commit (installed as a pre-commit hook: `ln -s ../../scripts/check-secrets.sh .git/hooks/pre-commit`).
