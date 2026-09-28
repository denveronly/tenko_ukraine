"""Config flow for Tenko."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TenkoApi, TenkoAuthError, TenkoError
from .const import CONF_LOGIN, CONF_TOKEN, DEFAULT_HOST, DOMAIN


async def _validate(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Try to read total_state; return it (for serial number) or raise."""
    api = TenkoApi(
        async_get_clientsession(hass),
        data[CONF_HOST],
        login=data.get(CONF_LOGIN) or None,
        password=data.get(CONF_PASSWORD) or None,
        token=data.get(CONF_TOKEN) or None,
    )
    return await api.get_total_state()


def _schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
            vol.Optional(CONF_LOGIN, default=defaults.get(CONF_LOGIN, "")): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Optional(CONF_TOKEN, default=""): str,
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    return {k: v.strip() for k, v in user_input.items() if isinstance(v, str) and v.strip()}


class TenkoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            if not data.get(CONF_TOKEN) and not (data.get(CONF_LOGIN) and data.get(CONF_PASSWORD)):
                errors["base"] = "missing_credentials"
            else:
                try:
                    state = await _validate(self.hass, data)
                except TenkoAuthError:
                    errors["base"] = "invalid_auth"
                except TenkoError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(str(state.get("SN") or data[CONF_HOST]))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=f"Tenko {state.get('SN', '')}".strip(), data=data)

        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_HOST: entry.data[CONF_HOST], **_clean(user_input)}
            try:
                await _validate(self.hass, data)
            except TenkoAuthError:
                errors["base"] = "invalid_auth"
            except TenkoError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LOGIN, default=entry.data.get(CONF_LOGIN, "")): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Optional(CONF_TOKEN, default=""): str,
                }
            ),
            errors=errors,
        )
