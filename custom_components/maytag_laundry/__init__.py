"""Maytag Laundry integration for Home Assistant.

Connects Whirlpool/Maytag/KitchenAid TS (Thing Shadow) laundry
appliances via AWS IoT MQTT.

Credits:
- abmantis/whirlpool-sixth-sense for Whirlpool OAuth reverse engineering
- TS appliance research documented in TS_APPLIANCE_API.md
"""
from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import WhirlpoolTSClient
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_BRAND
from .coordinator import MaytagLaundryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Maytag Laundry from a config entry."""
    session = aiohttp.ClientSession()
    client = WhirlpoolTSClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        brand=entry.data[CONF_BRAND],
        session=session,
    )

    coordinator = MaytagLaundryCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MaytagLaundryCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
