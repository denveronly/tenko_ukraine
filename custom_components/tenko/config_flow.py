"""Config flow for Tenko.

Asks for login/password once, exchanges them for a token via /auth and
stores only host + login + token in the config entry (HA .storage).
The password is not stored. If the token is ever rejected, HA starts
a reauth flow and asks for the password again.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TenkoApi, TenkoAuthError, TenkoError, async_get_token
from .const import (
    CONF_LOGIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    CONF_STAGE1_POWER,
    CONF_STAGE2_POWER,
    CONF_TOKEN,
    DEFAULT_HOST,
    DEFAULT_STAGE1_POWER,
    DEFAULT_STAGE2_POWER,
    DOMAIN,
    EP_TOTAL_STATE,
)


class TenkoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _login(self, host: str, login: str, password: str) -> tuple[str, dict[str, Any]]:
        """Get a token and check it works. Returns (token, total_state)."""
        session = async_get_clientsession(self.hass)
        token = await async_get_token(session, host, login, password)
        state = await TenkoApi(session, host, token).get(EP_TOTAL_STATE)
        return token, state

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            login = user_input[CONF_LOGIN].strip()
            try:
                token, state = await self._login(host, login, user_input[CONF_PASSWORD])
            except TenkoAuthError:
                errors["base"] = "invalid_auth"
            except TenkoError:
                errors["base"] = "cannot_connect"
            else:
                serial = str(state.get("SN") or login)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Tenko {serial}",
                    data={CONF_HOST: host, CONF_LOGIN: login, CONF_TOKEN: token},
                )

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOGIN, default=defaults.get(CONF_LOGIN, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            login = user_input[CONF_LOGIN].strip()
            try:
                token, _ = await self._login(entry.data[CONF_HOST], login, user_input[CONF_PASSWORD])
            except TenkoAuthError:
                errors["base"] = "invalid_auth"
            except TenkoError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_LOGIN: login, CONF_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOGIN, default=entry.data.get(CONF_LOGIN, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TenkoOptionsFlow()


class TenkoOptionsFlow(OptionsFlow):
    """Update interval and element power for the consumption estimate."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                    vol.Required(
                        CONF_STAGE1_POWER, default=opts.get(CONF_STAGE1_POWER, DEFAULT_STAGE1_POWER)
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                    vol.Required(
                        CONF_STAGE2_POWER, default=opts.get(CONF_STAGE2_POWER, DEFAULT_STAGE2_POWER)
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                }
            ),
        )
