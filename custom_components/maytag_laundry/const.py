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

# Fault code descriptions for Whirlpool/Maytag TS appliances.
# Codes are from capability profiles (W11771387 washer, W11771436 dryer)
# plus additional codes observed in the field.
# Fallback: raw code is displayed when no entry is found.
FAULT_DESCRIPTIONS: dict[str, str] = {
    # --- Washer fault codes (F-series) ---
    "F0E2": "Lid/door lock fault",
    "F0E3": "Unbalanced load",
    "F0E7": "Motor control fault",
    "F0E8": "Lid/door switch open during cycle",
    "F0E9": "Overcurrent on lid lock",
    "F2E2": "User interface disconnected",
    "F3E2": "Pressure sensor fault",
    "F5E1": "Lid lock failure — lid cannot lock",
    "F5E3": "Lid lock failure — lid cannot unlock",
    "F5E4": "Lid lock fault (thermal)",
    "F6E1": "Communication fault — main control to UI",
    "F6E2": "Communication fault — main control to motor",
    "F7E3": "Motor fault — speed error",
    "F7E4": "Motor fault — overcurrent",
    "F8E1": "Water inlet fault — no water detected",
    "F8E3": "Overflow fault",
    "F8E6": "Suds detected",
    "F9E1": "Drain fault — water not draining",
    # --- Dryer fault codes ---
    "F2E1": "Keypad/user interface fault",
    "F3E1": "Exhaust thermistor open/shorted",
    "F3E3": "Moisture sensor fault",
    "F7E1": "Motor fault",
    "F3E5": "Inlet thermistor fault",
    "F3E6": "Outlet thermistor fault",
    "F4E1": "Heating element fault",
    "F4E2": "Heating element relay fault",
    "F4E4": "High-limit thermostat fault",
    "F6E3": "Communication fault — main control to UI",
    "F9E3": "Vent blockage detected",
}
