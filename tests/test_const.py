"""Tests for const.py brand configuration."""
from custom_components.maytag_laundry.const import (
    DOMAIN,
    BRAND_CONFIG,
    CONF_BRAND,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_POLL_INTERVAL,
)


def test_domain():
    assert DOMAIN == "maytag_laundry"


def test_brand_config_has_all_brands():
    assert "Maytag" in BRAND_CONFIG
    assert "Whirlpool" in BRAND_CONFIG
    assert "KitchenAid" in BRAND_CONFIG


def test_brand_config_structure():
    for brand, config in BRAND_CONFIG.items():
        assert "client_credentials" in config, f"{brand} missing client_credentials"
        assert len(config["client_credentials"]) >= 1, f"{brand} has no credentials"
        for creds in config["client_credentials"]:
            assert "client_id" in creds, f"{brand} creds missing client_id"
            assert "client_secret" in creds, f"{brand} creds missing client_secret"
        assert "oauth_url" in config, f"{brand} missing oauth_url"
        assert "iot_endpoint" in config, f"{brand} missing iot_endpoint"
        assert "aws_region" in config, f"{brand} missing aws_region"


def test_default_poll_interval():
    assert DEFAULT_POLL_INTERVAL == 30
