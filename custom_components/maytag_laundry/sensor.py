"""Sensor entities for Maytag Laundry integration.

Sensor generation is driven by capability profiles — one per appliance model —
which declare every cycle, option, and valid value the appliance supports.

Capability document research, profile concept, and the fixture tooling used
to capture the bundled profiles were the work of Paul T. (pts211):
  https://github.com/pts211/ha-whirlpool-aws
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Optional

from .profiles import ApplianceProfile

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known appliance states and cycle phases.  These are firmware-level constants
# not present in the capability document; the list covers all values observed
# across Whirlpool/Maytag TS appliances.
# ---------------------------------------------------------------------------
_APPLIANCE_STATES = [
    "standby", "running", "paused", "endOfCycle",
    "delay", "remoteStart", "clean",
]
_CYCLE_PHASES = [
    "sensing", "filling", "soaking", "washing",
    "rinsing", "spinning", "draining", "cooling", "drying", "done",
]


def extract_appliance_type(state: dict) -> Optional[str]:
    """Detect whether a state payload is for a washer or dryer.

    The getState response has a top-level 'washer' or 'dryer' key.
    Used as a fallback when no capability profile is available.
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
        sensor_key: Sensor key string (see build_sensor_descriptions).
    """
    appliance = state.get(appliance_type)
    if appliance is None:
        return None

    # --- Common sensors ---
    if sensor_key == "appliance_state":
        return appliance.get("applianceState")

    if sensor_key == "cycle_name":
        return appliance.get("cycleName")

    if sensor_key == "cycle_phase":
        phase = appliance.get("currentPhase")
        return phase if phase else None  # suppress empty string when idle

    if sensor_key == "time_remaining":
        cycle_time = appliance.get("cycleTime", {})
        seconds = cycle_time.get("time")
        if seconds is None:
            return None
        return math.ceil(seconds / 60)

    if sensor_key == "door_status":
        return appliance.get("doorStatus")

    if sensor_key == "active_fault":
        return state.get("activeFault")

    if sensor_key == "last_fault":
        history = state.get("faultHistory", [])
        return next((f for f in history if f and f.lower() != "none"), None)

    if sensor_key == "remote_start_enable":
        val = state.get("remoteStartEnable")
        return "on" if val else "off" if val is not None else None

    # --- Common option sensors (present in both washer and dryer appliance dicts) ---
    if sensor_key == "extra_power":
        return appliance.get("extraPower")

    if sensor_key == "pets":
        return appliance.get("pets")

    # --- Washer-specific ---
    if sensor_key == "soil_level":
        return appliance.get("soilLevel")

    if sensor_key == "spin_speed":
        return appliance.get("spinSpeed")

    if sensor_key == "wash_temperature":
        return appliance.get("washTemperature")

    if sensor_key == "water_level":
        return appliance.get("waterLevel")

    if sensor_key == "extra_rinse":
        return appliance.get("extraRinse")

    if sensor_key == "dispenser":
        return appliance.get("dispenser")

    # --- Dryer-specific ---
    if sensor_key == "dry_temperature":
        return appliance.get("dryTemperature")

    if sensor_key == "dry_level":
        return appliance.get("dryLevel")

    if sensor_key == "wrinkle_shield":
        return appliance.get("wrinkleShield")

    if sensor_key == "steam":
        return appliance.get("steam")

    if sensor_key == "damp_dry":
        return appliance.get("dampDry")

    if sensor_key == "low_air_flow":
        val = appliance.get("lowAirFlow")
        return "on" if val else "off" if val is not None else None

    if sensor_key == "lint_trap":
        val = appliance.get("lintTrap")
        return "on" if val else "off" if val is not None else None

    if sensor_key == "drum_light":
        val = appliance.get("drumLight")
        return "on" if val else "off" if val is not None else None

    return None


# ---------------------------------------------------------------------------
# Sensor spec tables — (sensor_key, display_name, icon, profile_options_key)
# profile_options_key is the camelCase field name used in the capability doc.
# ---------------------------------------------------------------------------
_WASHER_OPTION_SENSOR_DEFS: list[tuple[str, str, str, str]] = [
    ("soil_level",       "Soil Level",       "mdi:layers",            "soilLevel"),
    ("spin_speed",       "Spin Speed",       "mdi:rotate-right",      "spinSpeed"),
    ("wash_temperature", "Wash Temperature", "mdi:thermometer-water", "washTemperature"),
    ("water_level",      "Water Level",      "mdi:cup-water",         "waterLevel"),
    ("extra_rinse",      "Extra Rinse",      "mdi:water-plus",        "extraRinse"),
    ("extra_power",      "Extra Power",      "mdi:lightning-bolt",    "extraPower"),
    ("dispenser",        "Dispenser",        "mdi:spray",             "dispenser"),
    ("pets",             "Pets",             "mdi:paw",               "pets"),
]

_DRYER_OPTION_SENSOR_DEFS: list[tuple[str, str, str, str]] = [
    ("dry_level",      "Dry Level",      "mdi:hair-dryer",    "dryLevel"),
    ("wrinkle_shield", "Wrinkle Shield", "mdi:iron",          "wrinkleShield"),
    ("steam",          "Steam",          "mdi:cloud",         "steam"),
    ("damp_dry",       "Damp Dry",       "mdi:water-outline", "dampDry"),
    ("extra_power",    "Extra Power",    "mdi:lightning-bolt","extraPower"),
    ("pets",           "Pets",           "mdi:paw",           "pets"),
]

# Boolean dryer diagnostic sensors — always added for dryers, no profile needed
_DRYER_BOOLEAN_SENSOR_DEFS: list[tuple[str, str, str]] = [
    ("low_air_flow", "Low Air Flow", "mdi:air-filter"),
    ("lint_trap",    "Lint Trap",    "mdi:filter"),
    ("drum_light",   "Drum Light",   "mdi:lightbulb"),
]


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
        """Describes a Maytag sensor entity."""

        sensor_key: str = ""

    def build_sensor_descriptions(
        appliance_type: str,
        profile: Optional[ApplianceProfile],
    ) -> list[MaytagSensorDescription]:
        """Build the sensor description list for one appliance.

        Base sensors are always included. Profile-driven option sensors are
        added when a capability profile is available for the model.
        Devices without a bundled profile continue to work with the base set.
        """
        descs: list[MaytagSensorDescription] = [
            MaytagSensorDescription(
                key="appliance_state",
                sensor_key="appliance_state",
                name="State",
                icon="mdi:washing-machine",
                device_class=SensorDeviceClass.ENUM,
                options=_APPLIANCE_STATES,
            ),
            MaytagSensorDescription(
                key="cycle_phase",
                sensor_key="cycle_phase",
                name="Cycle Phase",
                icon="mdi:rotate-3d-variant",
                device_class=SensorDeviceClass.ENUM,
                options=_CYCLE_PHASES,
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
                options=["open", "closed"],
            ),
            MaytagSensorDescription(
                key="active_fault",
                sensor_key="active_fault",
                name="Active Fault",
                icon="mdi:alert-circle-outline",
            ),
            MaytagSensorDescription(
                key="last_fault",
                sensor_key="last_fault",
                name="Last Fault",
                icon="mdi:alert-circle",
            ),
            MaytagSensorDescription(
                key="remote_start_enable",
                sensor_key="remote_start_enable",
                name="Remote Start",
                icon="mdi:remote",
                device_class=SensorDeviceClass.ENUM,
                options=["on", "off"],
            ),
        ]

        # Cycle name sensor — options come from the profile's cycle list
        if profile:
            descs.append(MaytagSensorDescription(
                key="cycle_name",
                sensor_key="cycle_name",
                name="Cycle",
                icon="mdi:state-machine",
                device_class=SensorDeviceClass.ENUM,
                options=profile.cycles,
            ))

        if appliance_type == "dryer":
            # Dry temperature: always present for dryers; prefer profile options
            dryer_temp_opts = (
                profile.options.get("dryTemperature")
                if profile else ["extraLow", "low", "medium", "high"]
            )
            descs.append(MaytagSensorDescription(
                key="dry_temperature",
                sensor_key="dry_temperature",
                name="Dry Temperature",
                icon="mdi:thermometer",
                device_class=SensorDeviceClass.ENUM,
                options=dryer_temp_opts,
            ))
            # Profile-driven dryer option sensors
            if profile:
                for s_key, name, icon, opt_key in _DRYER_OPTION_SENSOR_DEFS:
                    opts = profile.options.get(opt_key)
                    if opts:
                        descs.append(MaytagSensorDescription(
                            key=s_key,
                            sensor_key=s_key,
                            name=name,
                            icon=icon,
                            device_class=SensorDeviceClass.ENUM,
                            options=opts,
                        ))
            # Boolean diagnostic sensors — always present for dryers
            for s_key, name, icon in _DRYER_BOOLEAN_SENSOR_DEFS:
                descs.append(MaytagSensorDescription(
                    key=s_key,
                    sensor_key=s_key,
                    name=name,
                    icon=icon,
                    device_class=SensorDeviceClass.ENUM,
                    options=["on", "off"],
                ))

        elif appliance_type == "washer":
            if profile:
                for s_key, name, icon, opt_key in _WASHER_OPTION_SENSOR_DEFS:
                    opts = profile.options.get(opt_key)
                    if opts:
                        descs.append(MaytagSensorDescription(
                            key=s_key,
                            sensor_key=s_key,
                            name=name,
                            icon=icon,
                            device_class=SensorDeviceClass.ENUM,
                            options=opts,
                        ))

        return descs

    async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up Maytag sensor entities from a config entry."""
        coordinator: MaytagLaundryCoordinator = hass.data[DOMAIN][entry.entry_id]

        entities: list[MaytagSensorEntity] = []
        for said, device_data in coordinator.data.items():
            device = coordinator.client.devices.get(said)
            profile = device.profile if device else None

            # Capability profile cavities key is authoritative for appliance type.
            # Fall back to state inference for devices without a bundled profile.
            if profile:
                appliance_type = profile.appliance_type
            else:
                appliance_type = extract_appliance_type(device_data.get("state", {}))
                if appliance_type is None:
                    appliance_type = "washer"
                    _LOGGER.warning(
                        "Could not detect appliance type for %s, defaulting to washer", said
                    )

            for desc in build_sensor_descriptions(appliance_type, profile):
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
            if key in ("active_fault", "last_fault"):
                return {"fault_history": state.get("faultHistory", [])}
            return None

except ImportError:
    pass
