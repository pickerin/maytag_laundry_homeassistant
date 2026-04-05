# Maytag TS Appliance Home Assistant Integration — Design Spec

**Date:** 2026-04-05
**Status:** Approved
**Scope:** HACS-compatible custom integration for Maytag/Whirlpool/KitchenAid laundry appliances using the AWS IoT Thing Shadow (TS) API

## Overview

This integration connects newer Whirlpool-family laundry appliances (washers and dryers) to Home Assistant via AWS IoT MQTT. These "TS" (Thing Shadow) appliances are not supported by the existing `whirlpool-sixth-sense` library or the official HA Whirlpool integration. The TS API was reverse-engineered from the Maytag Android app; full findings are documented in `TS_APPLIANCE_API.md`.

### Credits

- **abmantis/whirlpool-sixth-sense** — original reverse engineering of the Whirlpool OAuth API, client credentials, backend selector architecture, and STOMP WebSocket protocol for legacy appliances
- **TS appliance API research** — documented in `TS_APPLIANCE_API.md`, covering the AWS IoT auth chain, MQTT topic structure, device discovery, and encrypted app configuration decryption

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Device scope | TS appliances only | Solves the actual problem. Legacy devices are served by the existing Whirlpool integration. |
| Brand/region scope | All NAR brands (Maytag, Whirlpool, KitchenAid) | Same IoT endpoint, minimal extra work — just a config flow dropdown. |
| Entity types | Sensors only (v1) | Safe read-only first release. Binary sensors and controls can be added later. |
| Update method | Hybrid: MQTT push + periodic poll | Push for responsiveness, poll as fallback for reliability. |
| MQTT approach | Own connection via awscrt | HA's MQTT integration cannot do SigV4 WebSocket auth. |
| Architecture | Layered with internal API module | Clean separation, independently testable, extractable to library later. |
| boto3 | Not used | Too heavy (~50MB). SigV4 signing via awscrt; Cognito calls via plain aiohttp. |

## File Structure

```
custom_components/maytag_laundry/
├── __init__.py          # Integration setup/teardown, platform forwarding
├── const.py             # Domain, config keys, default intervals, brand/region maps
├── config_flow.py       # Email/password + brand selector, validates auth, discovers TS devices
├── api.py               # Standalone async client: OAuth → Cognito → AWS IoT MQTT
├── coordinator.py       # HA DataUpdateCoordinator wrapping the API client
├── sensor.py            # Sensor entities (state, cycle, phase, time, temp, faults)
├── manifest.json        # HACS metadata, dependencies
└── translations/
    └── en.json          # UI strings for config flow and entities
```

## API Layer (`api.py`)

Standalone async class with zero HA imports. Pure async Python using `aiohttp` and `awscrt`.

### `WhirlpoolTSClient`

**Constructor:** `(email, password, brand, region, session: aiohttp.ClientSession)`

**Authentication chain (3 steps):**

1. `authenticate()` — OAuth password grant to `https://api.whrcloud.com/oauth/token` with brand-specific `client_id`/`client_secret`. Returns JWT containing `TS_SAID` array and `accountId`.
2. Cognito identity exchange — `GET /api/v1/cognito/identityid` with Bearer token. Returns `identityId` and `token`.
3. AWS credential exchange — `POST https://cognito-identity.us-east-2.amazonaws.com/` with Cognito token. Returns temporary `AccessKeyId`, `SecretKey`, `SessionToken` (valid ~1 hour).

Credentials are cached internally. OAuth token refresh uses `expires_in` from the JWT. AWS temp creds refresh proactively at the 45-minute mark.

**Device discovery:**

- `discover_devices()` — Decodes `TS_SAID` from the OAuth JWT. For each SAID, calls the AWS IoT `DescribeThing` API (direct HTTPS with SigV4 signing via `awscrt`, no boto3). Returns a list of device info dicts containing: `said`, `thing_type_name` (model prefix for MQTT topics), `brand`, `category`, `serial`, `name` (hex-decoded), `wifi_mac`.

**MQTT connection:**

- `connect()` — Establishes MQTT WebSocket connection to `wt.applianceconnect.net:443` using `mqtt_connection_builder.websockets_with_default_aws_signing()` from `awsiot`. Subscribes to state update and command response topics for all discovered devices.
- `disconnect()` — Clean MQTT teardown.

**State management:**

- `get_state(said)` — Publishes `getState` command to `cmd/{model}/{said}/request/{cognitoIdentityId}`. Returns the response payload via asyncio Future with a timeout.
- `register_callback(said, callback)` — Registers a callback for push updates arriving on `dt/{model}/{said}/state/update`.
- Internal state dict: `{said: {raw getState payload}}`.

### Brand/Region Configuration

Hardcoded in `const.py` (from decrypted app Data.json):

| Brand | Client ID | Region | IoT Endpoint |
|-------|-----------|--------|-------------|
| Maytag | `maytag_android_v2` | NAR | `wt.applianceconnect.net` |
| Whirlpool | `whirlpool_android_v2` | NAR | `wt.applianceconnect.net` |
| KitchenAid | `kitchenaid_android_v2` | NAR | `wt.applianceconnect.net` |

AWS region for all NAR brands: `us-east-2`.

### MQTT Topic Structure

All topics use: `{prefix}/{thingTypeName}/{said}/{suffix}`

| Purpose | Topic Pattern | Direction |
|---------|---------------|-----------|
| State updates (push) | `dt/{model}/{said}/state/update` | Subscribe |
| Command responses | `cmd/{model}/{said}/response/{cognitoIdentityId}` | Subscribe |
| Send commands | `cmd/{model}/{said}/request/{cognitoIdentityId}` | Publish |

**getState command payload:**
```json
{
  "requestId": "<uuid4>",
  "timestamp": "<epoch_ms>",
  "payload": {
    "addressee": "appliance",
    "command": "getState"
  }
}
```

## Coordinator (`coordinator.py`)

### `MaytagLaundryCoordinator(DataUpdateCoordinator)`

Bridges the API client and HA entity layer.

**Lifecycle:**
- Created in `__init__.py` `async_setup_entry()`, stored on `hass.data[DOMAIN][entry_id]`.
- On first refresh: calls `authenticate()`, `discover_devices()`, `connect()`.
- Torn down in `async_unload_entry()` via `client.disconnect()`.

**Update strategy (hybrid):**
- Registers a push callback per device that calls `async_set_updated_data()` on incoming MQTT messages.
- `_async_update_data()` polls `get_state()` for each device at a default interval of 30 seconds.
- On MQTT reconnect, triggers an immediate poll for all devices.

**Data shape exposed to entities:**
```python
{
    "WPR4BV39NFM8D": {
        "said": "WPR4BV39NFM8D",
        "model": "MTW7205RR0",
        "brand": "MAYTAG",
        "category": "LAUNDRY",
        "name": "Maytag Washer",
        "serial": "CE3600456",
        "online": True,
        "state": { ... }  # raw getState response payload
    }
}
```

## Sensor Entities (`sensor.py`)

Each TS device becomes one HA device. Sensors are grouped under that device.

**Device info** (from `describe_thing`):
- Name: hex-decoded friendly name (e.g., "Maytag Washer")
- Model: `thingTypeName` (e.g., "MTW7205RR0")
- Serial: from thing attributes
- Manufacturer: brand name ("Maytag" / "Whirlpool" / "KitchenAid")

### Washer Sensors

| Sensor | State Value | Device Class | Attributes |
|--------|-------------|--------------|------------|
| Appliance State | `running` / `idle` / `complete` / etc. | `enum` | cycle_name, cycle_type |
| Cycle Phase | `rinse` / `wash` / `spin` / etc. | `enum` | — |
| Time Remaining | minutes (integer) | `duration` | completion timestamp |
| Door Status | `closed` / `open` | `enum` | lock status |
| Active Fault | `none` / fault code string | `enum` | fault history list |

### Dryer Sensors

| Sensor | State Value | Device Class | Attributes |
|--------|-------------|--------------|------------|
| Appliance State | `running` / `idle` / `complete` / etc. | `enum` | cycle_name, cycle_type |
| Cycle Phase | `dry` / `cooldown` / etc. | `enum` | — |
| Time Remaining | minutes (integer) | `duration` | completion timestamp |
| Dry Temperature | `high` / `medium` / `low` / etc. | `enum` | — |
| Door Status | `closed` / `open` | `enum` | — |
| Active Fault | `none` / fault code string | `enum` | fault history list |

### Entity ID Convention

`sensor.maytag_laundry_{device_name}_{sensor_type}`

Example: `sensor.maytag_laundry_maytag_washer_state`, `sensor.maytag_laundry_maytag_dryer_time_remaining`

## Config Flow (`config_flow.py`)

### User Step

Form fields:
- **Email** (text input, required)
- **Password** (password input, required)
- **Brand** (dropdown: Maytag / Whirlpool / KitchenAid)

### Validation (behind the scenes)

1. OAuth login with selected brand credentials
2. Decode JWT — extract `TS_SAID` array
3. If empty: show error "No supported appliances found on this account"
4. Cognito identity exchange to confirm full auth chain
5. `describe_thing` for each SAID to get device metadata

### Entry Creation

- **Title:** "{Brand} Laundry" (e.g., "Maytag Laundry")
- **Unique ID:** account email (prevents duplicates)
- **Stored data:** email, password, brand, discovered devices dict (SAID → model/name/serial/category)

### Reauth Flow

When credentials fail, HA triggers reauth. Re-presents the user form, validates, updates stored credentials without removing entities.

## Dependencies

### `manifest.json` requirements

- `awsiotsdk` — provides both `awscrt` (SigV4 signing, MQTT transport) and `awsiot` (MQTT connection builder). Handles MQTT WebSocket connection and SigV4 HTTP signing for `DescribeThing` calls, eliminating the need for boto3. The `DescribeThing` call requires manual SigV4 request construction using `awscrt.auth` — this is the most complex part of the API layer but avoids pulling in ~50MB of boto3/botocore.

`aiohttp` is available in HA by default and does not need to be listed.

`whirlpool-sixth-sense` is removed — no longer needed.

### HACS metadata

`hacs.json` unchanged:
```json
{
  "name": "Maytag Washer & Dryer (Cloud)",
  "content_in_root": false,
  "homeassistant": "2025.7.2"
}
```

### License

MIT. README credits:
- `abmantis/whirlpool-sixth-sense` for original Whirlpool OAuth/API reverse engineering
- TS appliance research documented in `TS_APPLIANCE_API.md`

## Error Handling and Resilience

### MQTT Connection

- Auto-reconnect with exponential backoff: 5s → 15s → 60s → capped at 5 minutes. `awscrt` handles reconnection natively via connection builder configuration.
- On reconnect: immediate `getState` poll for all devices.

### Credential Refresh

- AWS temp creds (~1 hour lifetime): proactive refresh at the 45-minute mark.
- OAuth token: refresh based on `expires_in`. If refresh fails, re-run full auth chain with stored email/password.
- If stored password is invalid (user changed it): trigger HA reauth flow, mark all entities unavailable.

### Entity Availability

- Entities start as `unavailable` until first successful `getState` response.
- On MQTT disconnect: entities keep last known state (stale but useful).
- After 5 minutes with no updates from push or poll: entities go `unavailable`.

### Safety

- Validate model prefix from `describe_thing` before any MQTT publish. Publishing to a wrong topic causes an immediate server disconnect.
- Pace MQTT subscribes with 0.5s delay between each — the IoT policy is sensitive to rapid operations.
- All secrets (email, password, client credentials) stored in HA's config entry (encrypted at rest by HA).

### Logging

Standard HA `_LOGGER` conventions:
- **Debug:** MQTT message payloads, auth token refresh timing
- **Info:** connect/disconnect/reconnect events, device discovery results
- **Error:** auth failures, unrecoverable MQTT errors, malformed payloads
