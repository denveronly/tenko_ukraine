# Tenko Boiler — Home Assistant integration

A custom integration for the **Tenko** electric boiler that talks to its cloud API ([docs](https://my.tenko.ua/api/)). It replaces the Node-RED flow: no MQTT, no `input_number`/`input_boolean`.

## Installation

**HACS:** HACS → ⋮ → Custom repositories → the URL of this repo, category *Integration* → install → restart HA.

**Manually:** copy `custom_components/tenko` into `/config/custom_components/` and restart HA.

Then go to *Settings → Devices & Services → Add Integration → Tenko Boiler* and enter your **my.tenko.ua login and password**.

## Authorization and secrets

- On setup the integration calls `POST /api/v1/auth` itself and gets a token (one per user and boiler).
- **Only the token is stored** (plus login and server address) in HA's config entry (`/config/.storage`). **The password is not stored.**
- If the server ever rejects the token (401), HA shows a "Re-authenticate" notification: enter the password again and a new token is obtained.
- Everything runs over HTTPS (`https://my.tenko.ua`, the same server as `188.166.117.80`).
- There are no tokens or passwords in the repository; `scripts/check-secrets.sh` blocks a commit that accidentally contains one.

## Entities

| Type | Entity | API source |
|---|---|---|
| sensor | Air temperature, water feed / return temperature | `AT`, `WFT`, `RWFT` |
| sensor | Pressure (bar) | `PRS` |
| sensor | **Energy today** (kWh, resets at midnight) | estimate, see below |
| sensor | **Energy total** (kWh, for the Energy dashboard) | estimate |
| sensor | Estimated power (kW) | `HE1`/`HE2` × element power |
| sensor | Energy last N days (attribute `days`) | `STAT` |
| sensor | Energy last 12 months (attribute `months`) | `YSTAT` |
| sensor | Rated power, modulation, errors, boiler clock, firmware, serial number | `POW`, `MOD`, `ERR`, `BDT`, `VER`, `SN` |
| binary_sensor | Heating element 1 / 2, pump, antifreeze, error, modulation | `HE1`, `HE2`, `PMP`, `AF`, `ERR`, `MOD` |
| number | Water feed / return water feed + delta | `/water_feed`, `/returned_water_feed` |
| number | Constant air temperature | `/const_temp` |
| number | Maintain min temp: min / max | `/maintain_min_temp` |
| number | Pause 1 / Pause 2 | `/pauses` |
| switch | Stage 1 / Stage 2 | `/stages` |
| switch | Constant temperature, maintain min temperature, modulation | `/const_temp`, `/maintain_min_temp`, `/modulation` |
| select | Program: `Temp` / `WChart` (weekly) / `DChart` (daily) | `/used_chart_type` |

Current setpoints are read from `GET /settings`, `/const_temp` and `/used_chart_type` every minute, so changes made in the Tenko app show up in HA too.

## Daily consumption

The boiler (non-"smart" model) has no daily counter: `v1.2/smart/day_stat_state` returns `null`, `STAT` is a sliding window over N days, and `YSTAT` is a rolling 12 months with no month labels. So the integration calculates consumption itself: every minute it checks which heating elements are on and multiplies by their power.

Power defaults to **stage 1 = 7 kW, stage 2 = 14 kW** (21 kW total). It can be changed in *Integration → Configure*. The estimate ignores modulation and polls once a minute, so it is approximate. For exact numbers you need an electricity meter on the boiler line.

`sensor.tenko_energy_total` can be added to the **Energy dashboard**; a monthly counter can be built from it with `utility_meter` (`cycle: monthly`).

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```

Before committing, `scripts/check-secrets.sh` checks that no JWT/Bearer token got into the commit (installed as a pre-commit hook: `ln -s ../../scripts/check-secrets.sh .git/hooks/pre-commit`).
