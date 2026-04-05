"""Sensor entities for Maytag Laundry integration."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)


def extract_appliance_type(state: dict) -> Optional[str]:
    """Detect whether state payload is for a washer or dryer.

    The getState response has a top-level 'washer' or 'dryer' key.
    """
    if "washer" in state:
        return "washer"
    if "dryer" in state:
        return "dryer"
    return None


def extract_sensor_value(
    state: dict, appliance_type: str, sensor_key: str
) -> Any:
    """Extract a sensor value from the getState response payload.

    Args:
        state: The raw getState response payload.
        appliance_type: "washer" or "dryer".
        sensor_key: One of: appliance_state, cycle_phase, time_remaining,
                    door_status, active_fault, dry_temperature.
    """
    appliance = state.get(appliance_type)
    if appliance is None:
        return None

    if sensor_key == "appliance_state":
        return appliance.get("applianceState")

    if sensor_key == "cycle_phase":
        return appliance.get("currentPhase")

    if sensor_key == "time_remaining":
        cycle_time = appliance.get("cycleTime", {})
        seconds = cycle_time.get("time")
        if seconds is None:
            return None
        return math.ceil(seconds / 60)  # Convert to minutes, round up

    if sensor_key == "door_status":
        return appliance.get("doorStatus")

    if sensor_key == "active_fault":
        return state.get("activeFault")

    if sensor_key == "dry_temperature":
        return appliance.get("dryTemperature")

    return None


try:
    from homeassistant.components.sensor import (
        SensorDeviceClass,
        SensorEntity,
        SensorEntityDescription,
    )
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    from .const import DOMAIN
    from .coordinator import MaytagLaundryCoordinator

    @dataclass(frozen=True)
    class MaytagSensorDescription(SensorEntityDescription):
        """Describes a Maytag sensor."""

        sensor_key: str = ""
        appliance_types: tuple[str, ...] = ("washer", "dryer")

    SENSOR_DESCRIPTIONS: list[MaytagSensorDescription] = [
        MaytagSensorDescription(
            key="appliance_state",
            sensor_key="appliance_state",
            name="State",
            icon="mdi:washing-machine",
            device_class=SensorDeviceClass.ENUM,
        ),
        MaytagSensorDescription(
            key="cycle_phase",
            sensor_key="cycle_phase",
            name="Cycle Phase",
            icon="mdi:rotate-3d-variant",
            device_class=SensorDeviceClass.ENUM,
        ),
        MaytagSensorDescription(
            key="time_remaining",
            sensor_key="time_remaining",
            name="Time Remaining",
            icon="mdi:timer-outline",
            native_unit_of_measurement="min",
            device_class=SensorDeviceClass.DURATION,
        ),
        MaytagSensorDescription(
            key="door_status",
            sensor_key="door_status",
            name="Door",
            icon="mdi:door",
            device_class=SensorDeviceClass.ENUM,
        ),
        MaytagSensorDescription(
            key="active_fault",
            sensor_key="active_fault",
            name="Active Fault",
            icon="mdi:alert-circle-outline",
        ),
        MaytagSensorDescription(
            key="dry_temperature",
            sensor_key="dry_temperature",
            name="Dry Temperature",
            icon="mdi:thermometer",
            device_class=SensorDeviceClass.ENUM,
            appliance_types=("dryer",),
        ),
    ]

    async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up Maytag sensor entities from a config entry."""
        coordinator: MaytagLaundryCoordinator = hass.data[DOMAIN][entry.entry_id]

        entities: list[MaytagSensorEntity] = []
        for said, device_data in coordinator.data.items():
            appliance_type = extract_appliance_type(device_data.get("state", {}))
            if appliance_type is None:
                appliance_type = "washer"  # default fallback
                _LOGGER.warning(
                    "Could not detect type for %s, defaulting to washer", said
                )

            for desc in SENSOR_DESCRIPTIONS:
                if appliance_type in desc.appliance_types:
                    entities.append(
                        MaytagSensorEntity(coordinator, said, appliance_type, desc)
                    )

        async_add_entities(entities)

    class MaytagSensorEntity(
        CoordinatorEntity[MaytagLaundryCoordinator], SensorEntity
    ):
        """Sensor entity for a Maytag laundry appliance."""

        entity_description: MaytagSensorDescription

        def __init__(
            self,
            coordinator: MaytagLaundryCoordinator,
            said: str,
            appliance_type: str,
            description: MaytagSensorDescription,
        ) -> None:
            super().__init__(coordinator)
            self.entity_description = description
            self._said = said
            self._appliance_type = appliance_type

            device_data = coordinator.data.get(said, {})
            device_name = device_data.get("name", said)

            self._attr_unique_id = f"{said}_{description.key}"
            self._attr_has_entity_name = True

            self._attr_device_info = {
                "identifiers": {(DOMAIN, said)},
                "name": device_name,
                "manufacturer": device_data.get("brand", "Whirlpool"),
                "model": device_data.get("model", ""),
                "serial_number": device_data.get("serial", ""),
            }

        @property
        def native_value(self) -> Any:
            """Return the sensor value."""
            if self.coordinator.data is None:
                return None
            device_data = self.coordinator.data.get(self._said, {})
            state = device_data.get("state", {})
            return extract_sensor_value(
                state, self._appliance_type, self.entity_description.sensor_key
            )

        @property
        def available(self) -> bool:
            """Entity is available when we have state data."""
            if self.coordinator.data is None:
                return False
            device_data = self.coordinator.data.get(self._said, {})
            return device_data.get("online", False) and bool(device_data.get("state"))

        @property
        def extra_state_attributes(self) -> dict[str, Any] | None:
            """Return extra attributes based on sensor type."""
            if self.coordinator.data is None:
                return None
            device_data = self.coordinator.data.get(self._said, {})
            state = device_data.get("state", {})
            appliance = state.get(self._appliance_type, {})

            key = self.entity_description.sensor_key
            if key == "appliance_state":
                return {
                    "cycle_name": appliance.get("cycleName"),
                    "cycle_type": appliance.get("cycleType"),
                }
            if key == "time_remaining":
                cycle_time = appliance.get("cycleTime", {})
                return {"completion_timestamp": cycle_time.get("timeComplete")}
            if key == "door_status" and self._appliance_type == "washer":
                return {"lock_status": appliance.get("doorLockStatus")}
            if key == "active_fault":
                return {"fault_history": state.get("faultHistory", [])}
            return None

except ImportError:
    pass
