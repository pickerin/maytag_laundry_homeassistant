"""Tests for sensor state extraction."""
import json
from custom_components.maytag_laundry.sensor import (
    extract_appliance_type,
    extract_sensor_value,
)


WASHER_STATE = {
    "washer": {
        "applianceState": "running",
        "cycleName": "cleanWasher",
        "cycleType": "standard",
        "currentPhase": "rinse",
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
        "cycleName": "steamRefresh",
        "cycleType": "standard",
        "currentPhase": "dry",
        "dryTemperature": "high",
        "cycleTime": {"state": "running", "time": 1215, "timeComplete": 1775395276},
        "doorStatus": "closed",
    },
    "remoteStartEnable": False,
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
    def test_washer_appliance_state(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "appliance_state") == "running"

    def test_washer_cycle_name(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "cycle_phase") == "rinse"

    def test_washer_time_remaining_minutes(self):
        val = extract_sensor_value(WASHER_STATE, "washer", "time_remaining")
        assert val == 62  # 3665 seconds -> ceil(61.08) = 62 minutes

    def test_washer_door_status(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "door_status") == "closed"

    def test_washer_active_fault(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "active_fault") == "none"

    def test_dryer_appliance_state(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "appliance_state") == "running"

    def test_dryer_temperature(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "dry_temperature") == "high"

    def test_dryer_time_remaining(self):
        val = extract_sensor_value(DRYER_STATE, "dryer", "time_remaining")
        assert val == 21  # 1215 seconds -> 21 minutes (rounded up)

    def test_missing_state_returns_none(self):
        assert extract_sensor_value({}, "washer", "appliance_state") is None
