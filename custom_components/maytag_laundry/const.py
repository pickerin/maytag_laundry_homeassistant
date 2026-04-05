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
