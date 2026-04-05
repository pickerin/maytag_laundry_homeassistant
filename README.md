# Maytag Laundry — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![HA Version](https://img.shields.io/badge/HA-2025.7.2+-blue.svg)](https://www.home-assistant.io/)

Custom [HACS](https://hacs.xyz/) integration for **Maytag**, **Whirlpool**, and **KitchenAid** laundry appliances (washers and dryers) using the Whirlpool cloud API over AWS IoT MQTT.

## Features

- **Real-time updates** via MQTT push with automatic polling fallback
- **Washer sensors:** appliance state, cycle phase, time remaining, door status, active fault
- **Dryer sensors:** appliance state, cycle phase, time remaining, door status, active fault, dry temperature
- **Multi-brand support:** Maytag, Whirlpool, and KitchenAid
- **Device grouping:** sensors are grouped under their appliance in the HA device registry with model and serial number

### Sensors

| Sensor | Washer | Dryer | Example Values |
|--------|:------:|:-----:|----------------|
| State | ✅ | ✅ | `standby`, `running`, `complete`, `pause` |
| Cycle Phase | ✅ | ✅ | `wash`, `rinse`, `spin`, `dry` |
| Time Remaining | ✅ | ✅ | Minutes remaining (e.g. `42`) |
| Door | ✅ | ✅ | `open`, `closed` |
| Active Fault | ✅ | ✅ | `none`, `F0E3`, etc. |
| Dry Temperature | | ✅ | `high`, `medium`, `low` |

Additional attributes are exposed on some sensors:
- **State:** `cycle_name`, `cycle_type`
- **Time Remaining:** `completion_timestamp`
- **Door (washer):** `lock_status`
- **Active Fault:** `fault_history`

## Requirements

- Home Assistant 2025.7.2 or newer
- A Maytag, Whirlpool, or KitchenAid account with **newer (TS) connected appliances**
- [HACS](https://hacs.xyz/) installed

## Installation

1. Open **HACS** in Home Assistant
2. Click the three-dot menu (top right) → **Custom repositories**
3. Add `https://github.com/pickerin/maytag_laundry_homeassistant` with category **Integration**
4. Click **Add**
5. Search for "Maytag" in HACS and click **Download**
6. **Restart Home Assistant**

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Maytag Laundry**
3. Enter your email, password, and select your brand (Maytag, Whirlpool, or KitchenAid)
4. The integration will authenticate, discover your appliances, and create sensor entities

## Limitations

- **Only newer "TS" (Thing Shadow) appliances are supported.** These are appliances that communicate via AWS IoT MQTT. If your appliance uses the older Whirlpool REST API (non-TS), it will not be discovered by this integration. The official Maytag/Whirlpool mobile app works with both — this integration only supports the newer protocol.
- **No control support.** This integration is read-only (sensors). It does not support starting, stopping, or changing cycles remotely.
- **Cloud-dependent.** The integration requires an active internet connection and access to the Whirlpool cloud API. If the cloud service is down, sensors will become unavailable.
- **No EU region support.** Currently only the US (NAR) region is supported. EU appliances use different endpoints and have not been tested.
- **Credentials are not encrypted.** Your Whirlpool account email and password are stored in the Home Assistant config entry. Use a strong, unique password.

## How It Works

The integration authenticates through a multi-step chain:

1. **OAuth** — Email/password login to the Whirlpool cloud API using brand-specific app credentials
2. **Cognito Identity** — Exchanges the OAuth token for an AWS Cognito identity
3. **AWS Credentials** — Obtains temporary AWS credentials via Cognito
4. **AWS IoT MQTT** — Connects to the MQTT broker and subscribes to appliance state topics

State updates are pushed in real-time over MQTT. A polling fallback runs every 30 seconds to catch any missed updates.

## Credits

- [abmantis/whirlpool-sixth-sense](https://github.com/abmantis/whirlpool-sixth-sense) for original Whirlpool OAuth reverse engineering
- TS appliance protocol research documented in `TS_APPLIANCE_API.md`

## Disclaimer

This is an unofficial integration. It is not affiliated with, endorsed by, or supported by Maytag, Whirlpool, or KitchenAid. Use at your own risk.
