from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class MaytagLaundryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maytag Laundry."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # For now, just create an entry to prove the flow works.
            return self.async_create_entry(title="Maytag Laundry", data=user_input)

        schema = vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
        