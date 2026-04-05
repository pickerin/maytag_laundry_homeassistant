"""Data update coordinator for Maytag Laundry integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import WhirlpoolTSClient, AuthError
from .const import DOMAIN, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MaytagLaundryCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator that manages the WhirlpoolTSClient and provides data to entities."""

    def __init__(self, hass: HomeAssistant, client: WhirlpoolTSClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.client = client
        self._started = False

    async def _async_setup(self) -> None:
        """One-time setup: authenticate, discover devices, connect MQTT."""
        try:
            await self.client.authenticate()
            await self.client.discover_devices()
            await self.client.connect()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Setup failed: {err}") from err

        # Register push callbacks so MQTT updates trigger entity refresh
        for said in self.client.devices:
            self.client.register_callback(said, self._on_device_update)

        self._started = True

    def _on_device_update(self, said: str, state: dict | None) -> None:
        """Called by MQTT push or reconnect. Triggers HA entity update."""
        if state is None:
            _LOGGER.debug("Reconnect signal for %s, will poll on next interval", said)
            return

        if self.data is None:
            return
        if said in self.data:
            self.data[said]["state"] = state
            self.data[said]["online"] = True
            self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Poll all devices via getState — fallback for push updates."""
        if not self._started:
            await self._async_setup()

        data: Dict[str, Any] = {}

        for said, device in self.client.devices.items():
            try:
                state = await self.client.get_state(said)
                data[said] = {
                    "said": device.said,
                    "model": device.model,
                    "brand": device.brand,
                    "category": device.category,
                    "name": device.name,
                    "serial": device.serial,
                    "online": state is not None,
                    "state": state or {},
                }
            except AuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception:
                _LOGGER.exception("Failed to get state for %s", said)
                cached = self.client.get_cached_state(said)
                data[said] = {
                    "said": device.said,
                    "model": device.model,
                    "brand": device.brand,
                    "category": device.category,
                    "name": device.name,
                    "serial": device.serial,
                    "online": False,
                    "state": cached or {},
                }

        return data

    async def async_shutdown(self) -> None:
        """Disconnect MQTT on shutdown."""
        await self.client.disconnect()
