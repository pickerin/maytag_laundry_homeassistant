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
            # Disconnect any partially-established MQTT connection before re-raising
            # to avoid orphaned awscrt connections that would hold Python callback refs.
            try:
                await self.client.disconnect()
            except Exception:
                _LOGGER.debug("Error cleaning up client after setup failure (ignored)")
            raise UpdateFailed(f"Setup failed: {err}") from err

        # Register push callbacks so MQTT updates trigger entity refresh
        for said in self.client.devices:
            self.client.register_callback(said, self._on_device_update)

        self._started = True

    def _on_device_update(self, said: str, state: dict | None) -> None:
        """Called by MQTT push or reconnect. Schedules a coordinator refresh."""
        if state is None:
            _LOGGER.debug("Reconnect signal for %s, scheduling refresh", said)
        # async_request_refresh became a coroutine in HA 2026.4.x — calling it
        # without await silently discards the coroutine.  Use async_create_task
        # so it is actually scheduled on the event loop.
        self.hass.async_create_task(self.async_request_refresh())

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
        await super().async_shutdown()
        await self.client.disconnect()
