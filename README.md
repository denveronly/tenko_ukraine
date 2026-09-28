# Tenko Boiler — Home Assistant integration

A custom integration for the **Tenko** electric boiler that talks to its cloud API ([docs](https://my.tenko.ua/api/)). It replaces the Node-RED flow: no MQTT, no `input_number`/`input_boolean`.

## Icon

The integration ships its own icon and logo in `custom_components/tenko/brand/` (the red Tenko triangle from my.tenko.ua). Home Assistant **2026.3+** shows them automatically; older versions show a generic placeholder.

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
| sensor | **Energy this month** (kWh, boiler meter, resets on the 1st) | `YSTAT[11]` |
| sensor | Energy previous month | `YSTAT[10]` |
| sensor | Energy January … Energy December (attribute `year`) | `YSTAT` |
| sensor | Energy last 12 months (attribute: kWh per `YYYY-MM`) | `YSTAT` |
| sensor | Energy last N days (attribute `days`) | `STAT` |
| sensor | Rated power, modulation, errors, boiler clock, firmware, serial number | `POW`, `MOD`, `ERR`, `BDT`, `VER`, `SN` |
| binary_sensor | Heating element 1 / 2, pump, antifreeze, error, modulation | `HE1`, `HE2`, `PMP`, `AF`, `ERR`, `MOD` |
| number | Water feed / return water feed + delta | `/water_feed`, `/returned_water_feed` |
| number | Constant air temperature | `/const_temp` |
| number | Maintain min temp: min / max | `/maintain_min_temp` |
| number | Pause 1 / Pause 2 | `/pauses` |
| switch | Stage 1 / Stage 2 | `/stages` |
| switch | Constant temperature, maintain min temperature, modulation | `/const_temp`, `/maintain_min_temp`, `/modulation` |
| time | Off-peak start / Off-peak end (default 23:00–07:00) | stored in HA |
| binary_sensor | Off-peak (on inside the window; attrs `next_change`, `stages_to_restore`) | HA clock |
| switch | Turn off stages in peak / Restore stages after peak / Off-peak heating: stage 1, stage 2 | stored in HA |
| binary_sensor | Boiler online (data not older than 10 min) | `BDT` |
| sensor | Last data from boiler (timestamp) | `BDT` |
| button | Refresh | fetch now |
| select | Program: `Temp` / `WChart` (weekly) / `DChart` (daily) | `/used_chart_type` |

Current setpoints are read from `GET /settings`, `/const_temp` and `/used_chart_type` every minute, so changes made in the Tenko app show up in HA too.

## Monthly consumption

`YSTAT` is a rolling 12-month window: oldest month first, **last item = current month** (by the boiler clock `BDT`). This is the same mapping the official my.tenko.ua app uses for its yearly chart. The integration turns it into:

- `sensor.tenko_energy_january` … `sensor.tenko_energy_december`, each with a `year` attribute (the most recent occurrence of that month);
- `sensor.tenko_energy_this_month` and `sensor.tenko_energy_previous_month`;
- `sensor.tenko_energy_last_12_months` = sum, with a `{"2025-10": …, "2026-09": …}` attribute.

## Daily consumption

The boiler has no daily counter (`v1.2/smart/day_stat_state` returns `null` for non-"smart" boilers). Two options:

**1. From the boiler meter (recommended).** `Energy this month` only grows during the month, so `utility_meter` turns it into daily numbers:

```yaml
utility_meter:
  tenko_energy_daily:
    name: Tenko energy daily
    source: sensor.tenko_energy_this_month
    cycle: daily
```

The same sensor can go straight into the **Energy dashboard**.

**2. Estimate.** `Energy today` / `Energy total` are integrated every minute from which heating elements are on (`HE1`/`HE2`) × their power (default 7 + 14 kW, configurable in *Integration → Configure*). They ignore modulation, so they are approximate.

## Entity order

Home Assistant sorts a device's entities alphabetically inside each group (Controls, Sensors, Configuration, Diagnostic) and an integration cannot change that. So entity **names** start with a position number, e.g. `1. Stage 1`, `2. Stage 2`, `3. Modulation`, `4. Water feed` … and in Sensors `1. Water feed temperature`, `2. Return water temperature` … with all energy sensors last. **Entity IDs have no numbers** (`switch.tenko_stage_1`, `number.tenko_water_feed`), so automations are not affected. To drop the numbers from a name, rename the entity in HA.

## Data freshness

The server returns the **last snapshot the boiler sent**; it does not ask the boiler for new data, and neither GET requests nor commands make it refresh. If the boiler loses its internet connection, the server (and HA) keep showing old values. Check:

- `binary_sensor.tenko_boiler_online` — off when the boiler's data is older than 10 minutes (attribute `data_age_minutes`);
- `sensor.tenko_last_data_from_boiler` — when the boiler last reported (from its clock `BDT`).

The polling interval is set in *Integration → Configure* (10–3600 s, default 60). `button.tenko_refresh` fetches immediately.

## Off-peak (night tariff) control

- Set the window with `time.tenko_off_peak_start` / `time.tenko_off_peak_end` (default 23:00–07:00; windows over midnight are fine).
- Turn on `switch.tenko_turn_off_stages_in_peak`. Then, checked every minute:
  - outside the window, any stage that is on (turned on from HA, an automation or the Tenko app) is switched **off**, and it is remembered which ones were on;
  - turning a stage on from HA during peak is refused with an error;
  - when the window starts, the remembered stages are switched back **on** (if `switch.tenko_restore_stages_after_peak` is on).
- **Heating at off-peak start:** turn on `switch.tenko_off_peak_heating_stage_1` and/or `…_stage_2`. When the window starts, those stages are switched on (once per night; choosing one in the middle of the night applies it immediately).
- `binary_sensor.tenko_off_peak` shows whether it is off-peak right now.

These settings are stored in Home Assistant (not on the boiler) and survive restarts. The window uses Home Assistant's clock and time zone.

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```

Before committing, `scripts/check-secrets.sh` checks that no JWT/Bearer token got into the commit (installed as a pre-commit hook: `ln -s ../../scripts/check-secrets.sh .git/hooks/pre-commit`).
