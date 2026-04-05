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
        assert "client_id" in config, f"{brand} missing client_id"
        assert "client_secret" in config, f"{brand} missing client_secret"
        assert "oauth_url" in config, f"{brand} missing oauth_url"
        assert "iot_endpoint" in config, f"{brand} missing iot_endpoint"
        assert "aws_region" in config, f"{brand} missing aws_region"


def test_default_poll_interval():
    assert DEFAULT_POLL_INTERVAL == 30
