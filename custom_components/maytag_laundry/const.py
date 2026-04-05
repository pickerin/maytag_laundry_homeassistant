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

# Brand configurations (from TS_APPLIANCE_API.md, decrypted Data.json)
BRAND_CONFIG = {
    "Maytag": {
        "client_id": "maytag_android_v2",
        "client_secret": "ULTqdvvqK0O9XcSLO3nA2tJDTLFKxdaaeKrimPYdXvnLX_yUtPhxovESldBId0Tf",
        "oauth_url": "https://api.whrcloud.com/oauth/token",
        "base_url": "https://api.whrcloud.com",
        "iot_endpoint": "wt.applianceconnect.net",
        "aws_region": "us-east-2",
    },
    "Whirlpool": {
        "client_id": "whirlpool_android_v2",
        "client_secret": "rMVCgnKKhIjoorcRa7cpckh5irsomybd4tM9Ir3QxJxQZlzgWSeWpkkxmsRg1PL-",
        "oauth_url": "https://api.whrcloud.com/oauth/token",
        "base_url": "https://api.whrcloud.com",
        "iot_endpoint": "wt.applianceconnect.net",
        "aws_region": "us-east-2",
    },
    "KitchenAid": {
        "client_id": "kitchenaid_android_v2",
        "client_secret": "jd15ExiJdEt8UgLWBslwkzkQkmRGCR9lVSgeaqcPmFZQc9pgxtpjmaPSw3g-aRXG",
        "oauth_url": "https://api.whrcloud.com/oauth/token",
        "base_url": "https://api.whrcloud.com",
        "iot_endpoint": "wt.applianceconnect.net",
        "aws_region": "us-east-2",
    },
}
