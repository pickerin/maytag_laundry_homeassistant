"""Config flow for Maytag Laundry integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WhirlpoolTSClient, AuthError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_BRAND, CONF_DEVICES, BRAND_CONFIG

_LOGGER = logging.getLogger(__name__)


class MaytagLaundryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maytag Laundry."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial user form."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            brand = user_input[CONF_BRAND]

            # Prevent duplicate entries for the same account
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            try:
                devices = await self._validate_and_discover(email, password, brand)
            except AuthError as err:
                _LOGGER.error("Authentication failed: %s", err)
                errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"{brand} Laundry",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_BRAND: brand,
                            CONF_DEVICES: {
                                d.said: {
                                    "model": d.model,
                                    "brand": d.brand,
                                    "category": d.category,
                                    "serial": d.serial,
                                    "name": d.name,
                                }
                                for d in devices.values()
                            },
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict) -> FlowResult:
        """Handle reauth when credentials expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Ask for a new password and update the existing entry."""
        errors = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await self._validate_and_discover(
                    entry.data[CONF_EMAIL], password, entry.data[CONF_BRAND]
                )
            except AuthError as err:
                _LOGGER.error("Reauthentication failed: %s", err)
                errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_EMAIL: entry.data[CONF_EMAIL]},
            errors=errors,
        )

    async def _validate_and_discover(self, email: str, password: str, brand: str) -> dict:
        """Validate credentials and discover TS devices using HA's managed session."""
        session = async_get_clientsession(self.hass)
        client = WhirlpoolTSClient(
            email=email,
            password=password,
            brand=brand,
            session=session,
        )
        await client.authenticate()

        if not client.ts_saids:
            return {}

        await client.ensure_aws_credentials()
        await client.discover_devices()
        return client.devices

    @staticmethod
    def _schema(user_input: dict | None = None) -> vol.Schema:
        defaults = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, "")): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_BRAND, default=defaults.get(CONF_BRAND, "Maytag")): vol.In(
                    list(BRAND_CONFIG.keys())
                ),
            }
        )
