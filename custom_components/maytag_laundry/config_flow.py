from __future__ import annotations

import logging
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from whirlpool.auth import Auth
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.backendselector import BackendSelector, Brand, Region

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate_and_discover(hass: HomeAssistant, email: str, password: str) -> dict:
    """Validate credentials and fetch appliances. Raises on failure."""
    backend_selector = BackendSelector(Brand.Maytag, Region.US)

    async with aiohttp.ClientSession() as session:
        auth = Auth(backend_selector, email, password, session)
        await auth.do_auth(store=False)

        mgr = AppliancesManager(backend_selector, auth, session)
        ok = await mgr.fetch_appliances()
        if not ok:
            raise ValueError("Could not fetch appliances")

        # Collect what we can; you can refine this later.
        washers = [w.said for w in (mgr.washers or [])]
        dryers = [d.said for d in (mgr.dryers or [])]
        others = []
        for group in (mgr.aircons, mgr.ovens, mgr.refrigerators):
            if group:
                others.extend([a.said for a in group])

        return {
            "washers": washers,
            "dryers": dryers,
            "others": others,
        }


class MaytagLaundryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maytag Laundry."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            email = user_input["email"]
            password = user_input["password"]

            try:
                discovered = await _validate_and_discover(self.hass, email, password)
            except Exception as err:
                _LOGGER.exception("Auth/discovery failed: %s", err)
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._schema(),
                    errors={"base": "auth_failed"},
                )

            title = "Maytag Laundry"
            data = {
                "email": email,
                "password": password,
                "discovered": discovered,
            }
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(step_id="user", data_schema=self._schema())

    @staticmethod
    def _schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): str,
            }
        )