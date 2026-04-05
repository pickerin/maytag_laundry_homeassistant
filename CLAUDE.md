# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom HACS integration for Maytag/Whirlpool laundry appliances (washers and dryers) using the Whirlpool cloud API. Domain: `maytag_laundry`. Currently in early development — config flow authentication and appliance discovery are implemented; entity creation, polling coordinator, and API wrapper are stubs.

## Architecture

Standard Home Assistant custom component using async config flow and cloud polling (`iot_class: cloud_polling`).

- **config_flow.py** — User setup flow: collects email/password, authenticates via `whirlpool-sixth-sense` library, discovers appliances (washers/dryers), stores credentials and device list in config entry
- **coordinator.py** — Data update coordinator (stub, not yet implemented)
- **api.py** — API wrapper (stub, not yet implemented)
- **const.py** — Constants (`DOMAIN = "maytag_laundry"`)
- **__init__.py** — Integration setup (stub)

The integration depends on `whirlpool-sixth-sense==0.18.8` which provides `Auth`, `AppliancesManager`, and `BackendSelector` classes. Config flow is hardcoded to `Brand.Maytag` and `Region.US`.

## Key Dependencies

- `whirlpool-sixth-sense` — Third-party async library for Whirlpool cloud API (auth, appliance management, backend selection)
- `aiohttp` — Async HTTP (used by whirlpool lib and HA)
- `voluptuous` — Schema validation for config flow

## Development

No build system, test suite, or CI/CD is configured yet. No `setup.py` or `pyproject.toml`.

**Debugging tools:**
- `whirlpool_cli.py` — Interactive CLI for listing/connecting to appliances (supports multiple brands/regions via CLI args)
- `tools/whirlpool_smoketest.py` — Smoke test for auth and appliance discovery
- `tools/auth_probe.py` — Introspection of whirlpool package structure

**Local whirlpool library modifications:** The `.venv` contains a locally patched version of `whirlpool/auth.py` — check git status for local changes before updating the dependency.

## File Layout

All integration code lives in `custom_components/maytag_laundry/`. Translations are in `translations/en.json`. HACS metadata is in `hacs.json` at repo root. Minimum HA version: 2025.7.2.
