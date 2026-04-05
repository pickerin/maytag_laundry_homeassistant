# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom HACS integration for Maytag/Whirlpool laundry appliances (washers and dryers) using the Whirlpool TS (Thing Shadow) cloud API over AWS IoT MQTT. Domain: `maytag_laundry`. Version 1.0.0 — full implementation including auth, device discovery, real-time MQTT push, polling fallback, and sensor entities for Maytag, Whirlpool, and KitchenAid brands.

## Architecture

Standard Home Assistant custom component using async config flow and cloud push+poll (`iot_class: cloud_push`).

- **api.py** — Standalone async client (`WhirlpoolTSClient`). No HA dependencies. Implements the full auth chain: OAuth login → JWT decode of TS SAIDs → Cognito Identity exchange → AWS IoT MQTT. Provides device discovery via AWS IoT `describeThingShadow`, state subscriptions, and command publishing. Key exports: `WhirlpoolTSClient`, `AuthError`, `DeviceInfo`.
- **coordinator.py** — `MaytagLaundryCoordinator` (subclass of `DataUpdateCoordinator`). Hybrid push+poll: subscribes to MQTT state updates for low-latency delivery and falls back to periodic polling via `DEFAULT_POLL_INTERVAL`. Handles `AuthError` → `ConfigEntryAuthFailed` escalation.
- **config_flow.py** — User setup flow: collects email/password and brand selection (Maytag/Whirlpool/KitchenAid), authenticates via `WhirlpoolTSClient`, discovers TS appliances, stores credentials and device list in config entry.
- **sensor.py** — Sensor entity definitions. Pure helper functions `extract_appliance_type` and `extract_sensor_value` are HA-free and fully unit-tested. Supports washer and dryer state payloads: appliance state, cycle name, time remaining, door status, active fault, temperature.
- **const.py** — Constants: `DOMAIN = "maytag_laundry"`, `BRAND_CONFIG` (per-brand OAuth/Cognito endpoints for Maytag, Whirlpool, KitchenAid), `DEFAULT_POLL_INTERVAL`.
- **__init__.py** — Integration setup (entry load/unload, coordinator wiring).

### Auth Chain

```
Email/Password → Whirlpool OAuth (brand-specific endpoint)
    → Access token (JWT) → decode TS SAIDs (device identifiers)
    → Cognito GetId → Cognito GetCredentialsForIdentity
    → AWS IoT MQTT (awsiotsdk) with temporary credentials
```

## Key Dependencies

- `awsiotsdk>=1.0.0` — AWS IoT MQTT client (device state subscriptions and commands)
- `boto3>=1.20.0` — AWS Cognito Identity exchange for temporary credentials
- `aiohttp` — Async HTTP for OAuth and Cognito REST calls
- `voluptuous` — Schema validation for config flow

## Development

**Test suite:** `tests/` directory with 33 tests across three files. Run with:

```bash
.venv/bin/python -m pytest tests/ -v
```

Tests use `unittest.mock` stubs for the `homeassistant` namespace so no HA install is needed. All 33 tests pass.

**Import verification** (requires HA stubs, see `tests/conftest.py`):

```bash
.venv/bin/python -c "
import sys; from unittest.mock import MagicMock
for m in ['homeassistant','homeassistant.core','homeassistant.config_entries',
          'homeassistant.data_entry_flow','homeassistant.helpers',
          'homeassistant.helpers.update_coordinator','homeassistant.exceptions']:
    sys.modules[m] = MagicMock()
sys.modules['homeassistant.config_entries'].ConfigFlow = type('ConfigFlow', (), {})
from custom_components.maytag_laundry.const import DOMAIN, BRAND_CONFIG
from custom_components.maytag_laundry.api import WhirlpoolTSClient, AuthError, DeviceInfo
from custom_components.maytag_laundry.sensor import extract_appliance_type, extract_sensor_value
print('All imports OK', DOMAIN, list(BRAND_CONFIG.keys()))
"
```

**Debugging tools:**
- `whirlpool_cli.py` — Interactive CLI for listing/connecting to appliances (supports multiple brands/regions via CLI args)
- `tools/ts_mqtt.py` — Live MQTT debug tool for TS appliances (requires real credentials)
- `tools/whirlpool_smoketest.py` — Smoke test for auth and appliance discovery
- `tools/auth_probe.py` — Introspection of whirlpool package structure

## File Layout

```
custom_components/maytag_laundry/
    __init__.py        Integration setup
    api.py             Standalone WhirlpoolTSClient (OAuth→Cognito→MQTT)
    config_flow.py     User setup flow (brand + credentials)
    const.py           DOMAIN, BRAND_CONFIG, DEFAULT_POLL_INTERVAL
    coordinator.py     Hybrid push+poll coordinator
    manifest.json      HACS/HA metadata (version 1.0.0)
    sensor.py          Sensor entity definitions and helpers
    translations/
        en.json        Config flow strings

tests/
    conftest.py        HA namespace stubs
    test_api.py        API client unit tests (OAuth, JWT, Cognito, MQTT topics)
    test_const.py      Constants and brand config tests
    test_sensor.py     Sensor extraction helper tests
```

HACS metadata is in `hacs.json` at repo root. Minimum HA version: 2025.7.2.
