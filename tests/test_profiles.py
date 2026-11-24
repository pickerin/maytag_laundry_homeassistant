"""Tests for appliance capability profile loading and parsing."""
from custom_components.maytag_laundry.profiles import load_profile, _parse_profile


# Minimal capability document structure matching the real schema
_WASHER_CAP = {
    "capabilityFileSchemaVersion": "0.4.0",
    "partNumber": "W11771387",
    "cavities": {
        "washer": {
            "cycles": {
                "regularNormal": {
                    "etr": 3600,
                    "whrOptions": {
                        "requiredOptions": {
                            "washTemperature": {
                                "enumeration": ["tapCold", "cold", "warm", "hot"],
                            },
                            "soilLevel": {
                                "enumeration": ["light", "normal", "heavy"],
                            },
                        },
                        "optionalOptions": {
                            "extraRinse": {
                                "enumeration": ["off", "+1"],
                            },
                        },
                    },
                },
                "handWash": {
                    "etr": 600,
                    "whrOptions": {
                        "requiredOptions": {
                            "washTemperature": {
                                "enumeration": ["tapCold", "cold", "cool"],
                            },
                        },
                        "optionalOptions": {},
                    },
                },
            }
        }
    },
}

_DRYER_CAP = {
    "capabilityFileSchemaVersion": "0.4.0",
    "partNumber": "W11771436",
    "cavities": {
        "dryer": {
            "cycles": {
                "ecoEnergy": {
                    "etr": 0,
                    "whrOptions": {
                        "requiredOptions": {
                            "dryTemperature": {
                                "enumeration": ["extraLow", "low", "medium", "high"],
                            },
                            "dryLevel": {
                                "enumeration": ["lessDry", "normalDry", "extraDry"],
                            },
                        },
                        "optionalOptions": {},
                    },
                }
            }
        }
    },
}


class TestParseProfile:
    def test_washer_appliance_type(self):
        profile = _parse_profile("W11771387", _WASHER_CAP)
        assert profile.appliance_type == "washer"

    def test_dryer_appliance_type(self):
        profile = _parse_profile("W11771436", _DRYER_CAP)
        assert profile.appliance_type == "dryer"

    def test_washer_cycles_extracted(self):
        profile = _parse_profile("W11771387", _WASHER_CAP)
        assert "regularNormal" in profile.cycles
        assert "handWash" in profile.cycles
        assert len(profile.cycles) == 2

    def test_dryer_cycles_extracted(self):
        profile = _parse_profile("W11771436", _DRYER_CAP)
        assert "ecoEnergy" in profile.cycles

    def test_options_union_across_cycles(self):
        # washTemperature appears in both cycles with different values — expect union
        profile = _parse_profile("W11771387", _WASHER_CAP)
        temps = profile.options["washTemperature"]
        assert "tapCold" in temps
        assert "cold" in temps
        assert "warm" in temps
        assert "hot" in temps
        assert "cool" in temps  # only in handWash

    def test_optional_options_included(self):
        profile = _parse_profile("W11771387", _WASHER_CAP)
        assert "extraRinse" in profile.options
        assert "off" in profile.options["extraRinse"]

    def test_part_number_stored(self):
        profile = _parse_profile("W11771387", _WASHER_CAP)
        assert profile.part_number == "W11771387"

    def test_no_duplicate_values_in_union(self):
        # "tapCold" and "cold" appear in both cycles — should not be duplicated
        profile = _parse_profile("W11771387", _WASHER_CAP)
        temps = profile.options["washTemperature"]
        assert temps.count("tapCold") == 1
        assert temps.count("cold") == 1


class TestLoadProfile:
    def test_load_known_washer_profile(self):
        profile = load_profile("W11771387")
        assert profile is not None
        assert profile.appliance_type == "washer"
        assert profile.part_number == "W11771387"
        assert len(profile.cycles) > 0

    def test_load_known_dryer_profile(self):
        profile = load_profile("W11771436")
        assert profile is not None
        assert profile.appliance_type == "dryer"
        assert profile.part_number == "W11771436"
        assert len(profile.cycles) > 0

    def test_load_unknown_returns_none(self):
        assert load_profile("W99999999") is None

    def test_load_empty_string_returns_none(self):
        assert load_profile("") is None

    def test_washer_profile_has_expected_cycles(self):
        profile = load_profile("W11771387")
        assert "regularNormal" in profile.cycles
        assert "handWash" in profile.cycles

    def test_dryer_profile_has_expected_cycles(self):
        profile = load_profile("W11771436")
        assert "ecoEnergy" in profile.cycles
        assert "quickDryCottons" in profile.cycles

    def test_washer_profile_has_wash_temperature_options(self):
        profile = load_profile("W11771387")
        assert "washTemperature" in profile.options
        assert "cold" in profile.options["washTemperature"]
        assert "warm" in profile.options["washTemperature"]

    def test_dryer_profile_has_dry_temperature_options(self):
        profile = load_profile("W11771436")
        assert "dryTemperature" in profile.options
        assert "medium" in profile.options["dryTemperature"]
        assert "high" in profile.options["dryTemperature"]

    def test_load_front_load_washer_profile(self):
        # MFW7020RU0, contributed by ewilson1983
        profile = load_profile("W11812024")
        assert profile is not None
        assert profile.appliance_type == "washer"
        assert "normal" in profile.cycles
        assert "cleanWasher1" in profile.cycles
        assert "extraHot" in profile.options["washTemperature"]

    def test_load_med7020_dryer_profile(self):
        # MED7020RU0, contributed by ewilson1983
        profile = load_profile("W11804872")
        assert profile is not None
        assert profile.appliance_type == "dryer"
        assert "normal" in profile.cycles
        assert "airOnly" in profile.options["dryTemperature"]

    def test_front_load_washer_gets_steam_sensor(self):
        from custom_components.maytag_laundry.sensor import (
            build_sensor_descriptions,
            extract_sensor_value,
        )
        descs = {d.key: d for d in build_sensor_descriptions("washer", load_profile("W11812024"))}
        assert descs["steam"].options == ["off", "on"]
        # Captured standby state of an MFW7020RU0 after a Clean Washer cycle
        state = {"washer": {"cycleName": "cleanWasher1", "steam": "on"}}
        assert extract_sensor_value(state, "washer", "steam") == "on"

    def test_top_load_washer_has_no_steam_sensor(self):
        from custom_components.maytag_laundry.sensor import build_sensor_descriptions
        keys = [d.key for d in build_sensor_descriptions("washer", load_profile("W11771387"))]
        assert "steam" not in keys
