"""Tests for sensor state extraction."""
from custom_components.maytag_laundry.sensor import (
    extract_appliance_type,
    extract_sensor_value,
)


WASHER_STATE = {
    "washer": {
        "applianceState": "running",
        "cycleName": "regularNormal",
        "cycleType": "standard",
        "currentPhase": "rinse",
        "soilLevel": "heavy",
        "spinSpeed": "fast",
        "washTemperature": "warm",
        "waterLevel": "auto",
        "extraRinse": "off",
        "extraPower": "off",
        "dispenser": "off",
        "pets": "on",
        "cycleTime": {"state": "running", "time": 3665, "timeComplete": 1775397826},
        "doorStatus": "closed",
        "doorLockStatus": True,
    },
    "remoteStartEnable": False,
    "faultHistory": ["F0E3", "F8E6", "none", "none", "none"],
    "activeFault": "none",
}

DRYER_STATE = {
    "dryer": {
        "applianceState": "running",
        "cycleName": "ecoEnergy",
        "cycleType": "standard",
        "currentPhase": "dry",
        "dryTemperature": "high",
        "dryLevel": "normalDry",
        "wrinkleShield": "on",
        "steam": "on",
        "dampDry": "off",
        "extraPower": "off",
        "pets": "on",
        "lowAirFlow": True,
        "lintTrap": False,
        "drumLight": False,
        "cycleTime": {"state": "running", "time": 1215, "timeComplete": 1775395276},
        "doorStatus": "closed",
    },
    "remoteStartEnable": True,
    "faultHistory": ["none", "none", "none", "none", "none"],
    "activeFault": "none",
}


class TestApplianceTypeDetection:
    def test_washer_detected(self):
        assert extract_appliance_type(WASHER_STATE) == "washer"

    def test_dryer_detected(self):
        assert extract_appliance_type(DRYER_STATE) == "dryer"

    def test_unknown_returns_none(self):
        assert extract_appliance_type({"other": {}}) is None

    def test_empty_returns_none(self):
        assert extract_appliance_type({}) is None


class TestSensorValueExtraction:
    # --- Common sensors ---
    def test_washer_appliance_state(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "appliance_state") == "running"

    def test_washer_cycle_name(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "cycle_name") == "regularNormal"

    def test_washer_cycle_phase(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "cycle_phase") == "rinse"

    def test_cycle_phase_empty_returns_none(self):
        state = {"washer": {"currentPhase": ""}}
        assert extract_sensor_value(state, "washer", "cycle_phase") is None

    def test_washer_time_remaining_minutes(self):
        val = extract_sensor_value(WASHER_STATE, "washer", "time_remaining")
        assert val == 62  # 3665 seconds -> ceil(61.08) = 62 minutes

    def test_washer_door_status(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "door_status") == "closed"

    def test_washer_active_fault(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "active_fault") == "none"

    def test_washer_last_fault(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "last_fault") == "Unbalanced load"

    def test_washer_remote_start_off(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "remote_start_enable") == "off"

    def test_dryer_remote_start_on(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "remote_start_enable") == "on"

    # --- Washer option sensors ---
    def test_washer_soil_level(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "soil_level") == "heavy"

    def test_washer_spin_speed(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "spin_speed") == "fast"

    def test_washer_wash_temperature(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "wash_temperature") == "warm"

    def test_washer_water_level(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "water_level") == "auto"

    def test_washer_extra_rinse(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "extra_rinse") == "off"

    def test_washer_extra_power(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "extra_power") == "off"

    def test_washer_dispenser(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "dispenser") == "off"

    def test_washer_pets(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "pets") == "on"

    # --- Dryer sensors ---
    def test_dryer_appliance_state(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "appliance_state") == "running"

    def test_dryer_cycle_name(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "cycle_name") == "ecoEnergy"

    def test_dryer_temperature(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "dry_temperature") == "high"

    def test_dryer_dry_level(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "dry_level") == "normalDry"

    def test_dryer_wrinkle_shield(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "wrinkle_shield") == "on"

    def test_dryer_steam(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "steam") == "on"

    def test_dryer_damp_dry(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "damp_dry") == "off"

    def test_dryer_extra_power(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "extra_power") == "off"

    def test_dryer_pets(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "pets") == "on"

    def test_dryer_time_remaining(self):
        val = extract_sensor_value(DRYER_STATE, "dryer", "time_remaining")
        assert val == 21  # 1215 seconds -> ceil(20.25) = 21 minutes

    # --- Dryer boolean sensors ---
    def test_dryer_low_air_flow_on(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "low_air_flow") == "on"

    def test_dryer_lint_trap_off(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "lint_trap") == "off"

    def test_dryer_drum_light_off(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "drum_light") == "off"

    # --- Edge cases ---
    def test_missing_state_returns_none(self):
        assert extract_sensor_value({}, "washer", "appliance_state") is None

    def test_remote_start_missing_returns_none(self):
        assert extract_sensor_value({"washer": {}}, "washer", "remote_start_enable") is None

    def test_boolean_sensor_missing_returns_none(self):
        assert extract_sensor_value({"dryer": {}}, "dryer", "low_air_flow") is None
