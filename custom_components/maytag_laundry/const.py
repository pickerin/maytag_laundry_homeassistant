"""Constants for the Maytag Laundry integration."""

DOMAIN = "maytag_laundry"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BRAND = "brand"
CONF_DEVICES = "devices"

# Polling
DEFAULT_POLL_INTERVAL = 30  # seconds
STALE_TIMEOUT = 300  # 5 minutes — mark unavailable after this

# Brand configurations
# Each brand has a list of client credential sets to try in order.
# Primary: _v2 credentials from latest whirlpool-sixth-sense (master).
# Fallback: legacy credentials from older library versions.
BRAND_CONFIG = {
    "Maytag": {
        "client_credentials": [
            {
                "client_id": "maytag_android_v2",
                "client_secret": "ULTqdvvqK0O9XcSLO3nA2tJDTLFKxdaaeKrimPYdXvnLX_yUtPhxovESldBId0Tf",
            },
            {
                "client_id": "maytag_ios",
                "client_secret": "OfTy3A3rV4BHuhujkPThVDE9-SFgOymJyUrSbixjViATjCGviXucSKq2OxmPWm8DDj9D1IFno_mZezTYduP-Ig",
            },
        ],
        "oauth_url": "https://api.whrcloud.com/oauth/token",
        "base_url": "https://api.whrcloud.com",
        "iot_endpoint": "wt.applianceconnect.net",
        "aws_region": "us-east-2",
    },
    "Whirlpool": {
        "client_credentials": [
            {
                "client_id": "whirlpool_android_v2",
                "client_secret": "rMVCgnKKhIjoorcRa7cpckh5irsomybd4tM9Ir3QxJxQZlzgWSeWpkkxmsRg1PL-",
            },
            {
                "client_id": "whirlpool_android",
                "client_secret": "i-eQ8MD4jK4-9DUCbktfg-t_7gvU-SrRstPRGAYnfBPSrHHt5Mc0MFmYymU2E2qzif5cMaBYwFyFgSU6NTWjZg",
            },
        ],
        "oauth_url": "https://api.whrcloud.com/oauth/token",
        "base_url": "https://api.whrcloud.com",
        "iot_endpoint": "wt.applianceconnect.net",
        "aws_region": "us-east-2",
    },
    "KitchenAid": {
        "client_credentials": [
            {
                "client_id": "kitchenaid_android_v2",
                "client_secret": "jd15ExiJdEt8UgLWBslwkzkQkmRGCR9lVSgeaqcPmFZQc9pgxtpjmaPSw3g-aRXG",
            },
            {
                "client_id": "Kitchenaid_iOS",
                "client_secret": "kkdPquOHfNH-iIinccTdhAkJmaIdWBhLehhLrfoXRWbKjEpqpdu92PISF_yJEWQs72D2yeC0PdoEKeWgHR9JRA",
            },
        ],
        "oauth_url": "https://api.whrcloud.com/oauth/token",
        "base_url": "https://api.whrcloud.com",
        "iot_endpoint": "wt.applianceconnect.net",
        "aws_region": "us-east-2",
    },
}

# Fault code descriptions, keyed by appliance type because the same code
# means different things on a washer and a dryer (e.g. F7E1).
# Only codes backed by Maytag/Whirlpool help pages or Whirlpool tech sheets
# are listed (sources: https://gist.github.com/lacroixdavid1/4e1b29d41f1a788581a9a4f80618ed43,
# researched on an MTW7205RF1 top-load washer and YMED7205RF0 dryer).
# Codes not listed here get no description; the sensor state is always the raw code.
FAULT_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "washer": {
        "F0E2": "Over-suds detected",
        "F0E3": "Overload - load too large or basket cannot turn",
        "F0E4": "Water too hot - final spin speed limited",
        "F0E5": "Off-balance load",
        "F0E7": "Load detected during Clean Washer cycle",
        "F0E8": "Water left in tub",
        "F0E9": "Off-balance load - cycle paused",
        "F1E1": "Main control fault",
        "F1E2": "Motor drive over-voltage",
        "F2E1": "Stuck button on control panel",
        "F2E2": "User interface disconnected",
        "F2E3": "Main control / user interface mismatch",
        "F2E4": "User interface fault",
        "F2E5": "User interface fault",
        "F3E1": "Water level cannot be detected",
        "F3E2": "Pressure (water level) sensor fault",
        "F3E3": "Inlet water thermistor fault",
        "F3E5": "Bulk dispenser level sensor fault",
        "F5E1": "Lid switch reads open while lid is locked",
        "F5E2": "Lid lock will not lock",
        "F5E3": "Lid lock will not unlock or lock",
        "F5E4": "Lid not opened between cycles",
        "F6E1": "Communication fault - user interface cannot reach main control",
        "F6E2": "Communication fault - main control / user interface",
        "F6E3": "Communication fault - main control cannot reach motor control",
        "F7E1": "Motor speed sensor fault",
        "F7E2": "Motor drive failure",
        "F7E3": "Shifter fault - basket engaged during wash",
        "F7E4": "Shifter fault - basket failed to re-engage",
        "F7E6": "Motor circuit open",
        "F7E7": "Motor unable to reach target speed",
        "F7E8": "Motor drive over-temperature",
        "F7E9": "Locked rotor - motor not turning",
        "F7EA": "Motor phase lost",
        "F8E1": "Long fill - not enough water detected",
        "F8E2": "Bulk dispenser system failure",
        "F8E3": "Overflow - water level above capacity",
        "F8E6": "Water in tub with lid open over 10 minutes",
        "F9E1": "Long drain - water not draining",
    },
    "dryer": {
        "F1E3": "Main control fault",
        "F2E1": "Stuck button on control panel",
        "F2E2": "User interface disconnected",
        "F2E5": "User interface fault",
        "F3E1": "Exhaust thermistor open or shorted",
        "F3E2": "Moisture sensor fault",
        "F3E3": "Inlet thermistor open or shorted",
        "F3E5": "Moisture sensor fault",
        "F4E1": "Heater system fault",
        "F4E3": "Restricted airflow - check vent and lint screen",
        "F4E4": "Low or no L2 line voltage",
        "F6E1": "Communication fault - user interface cannot reach main control",
        "F6E3": "Communication fault - main control cannot reach user interface",
        "F7E1": "Motor system fault",
    },
}
