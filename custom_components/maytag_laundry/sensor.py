"""Sensor entities for Maytag Laundry integration."""
from __future__ import annotations

import math
from typing import Any, Optional


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
