# Maytag Laundry — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![HA Version](https://img.shields.io/badge/HA-2025.7.2+-blue.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-1.1.0-green.svg)](https://github.com/pickerin/maytag_laundry_homeassistant/releases)

Custom [HACS](https://hacs.xyz/) integration for **Maytag**, **Whirlpool**, and **KitchenAid** laundry appliances (washers and dryers) using the Whirlpool cloud API over AWS IoT MQTT.

## Features

- **Real-time updates** via MQTT push with automatic polling fallback
- **Capability-driven sensor discovery** — appliance profiles are loaded from bundled AWS IoT capability documents, so sensors and their valid values are specific to your exact model
- **Comprehensive washer sensors:** state, cycle, cycle phase, time remaining, door, fault tracking, soil level, spin speed, wash temperature, water level, extra rinse, extra power, dispenser, pets, remote start
- **Comprehensive dryer sensors:** state, cycle, cycle phase, time remaining, door, fault tracking, dry temperature, dry level, wrinkle shield, steam, damp dry, extra power, pets, remote start, low air flow, lint trap, drum light
- **Multi-brand support:** Maytag, Whirlpool, and KitchenAid
- **Device grouping:** all sensors are grouped under their appliance in the HA device registry with model and serial number

## Sensors

### Washer

| Sensor | Example Values | Notes |
|--------|---------------|-------|
| State | `standby`, `running`, `paused`, `endOfCycle` | |
| Cycle | `regularNormal`, `handWash`, `bulkyNormal`, … | All cycles from capability profile |
| Cycle Phase | `sensing`, `filling`, `rinsing`, `spinning`, … | |
| Time Remaining | `42` (min) | |
| Door | `open`, `closed` | Attribute: `lock_status` |
| Active Fault | `none`, `F0E3`, … | Attribute: `fault_history` |
| Last Fault | `F0E3`, … | Most recent non-none fault code |
| Remote Start | `on`, `off` | |
| Soil Level | `light`, `normal`, `heavy`, `extraHeavy`, … | |
| Spin Speed | `off`, `fast`, … | |
| Wash Temperature | `tapCold`, `cold`, `cool`, `warm`, `hot` | |
| Water Level | `auto`, `medium`, `high` | |
| Extra Rinse | `off`, `+1` | |
| Extra Power | `off`, `on` | |
| Dispenser | `off`, `softenerOnly`, … | |
| Pets | `off`, `on` | |

Additional attributes on **State**: `cycle_name`, `cycle_type`  
Additional attribute on **Time Remaining**: `completion_timestamp`

### Dryer

| Sensor | Example Values | Notes |
|--------|---------------|-------|
| State | `standby`, `running`, `paused`, `endOfCycle` | |
| Cycle | `ecoEnergy`, `quickDryCottons`, `steamRefresh`, … | All cycles from capability profile |
| Cycle Phase | `drying`, `cooling`, `done`, … | |
| Time Remaining | `35` (min) | |
| Door | `open`, `closed` | |
| Active Fault | `none`, `F0E3`, … | Attribute: `fault_history` |
| Last Fault | `F0E3`, … | Most recent non-none fault code |
| Remote Start | `on`, `off` | |
| Dry Temperature | `extraLow`, `low`, `medium`, `high` | |
| Dry Level | `lessDry`, `normalDry`, `extraDry` | |
| Wrinkle Shield | `off`, `on`, `onWithSteam` | |
| Steam | `off`, `on`, `reduceStatic`, `steamAndReduceStatic` | |
| Damp Dry | `off`, `on` | |
| Extra Power | `off`, `on` | |
| Pets | `off`, `on` | |
| Low Air Flow | `on`, `off` | Vent restriction warning |
| Lint Trap | `on`, `off` | Lint screen indicator |
| Drum Light | `on`, `off` | |

Additional attributes on **State**: `cycle_name`, `cycle_type`  
Additional attribute on **Time Remaining**: `completion_timestamp`

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

## Supported Models

Sensor availability is determined by the appliance's capability profile. Full sensor sets are currently available for:

| Part Number | Model | Type |
|-------------|-------|------|
| W11771387 | MTW7205RR0 | Maytag Top-Load Washer |
| W11771436 | MGD7205RR0 | Maytag Gas Dryer |

Appliances with other part numbers will still connect and report the 7 base sensors (state, cycle phase, time remaining, door, active fault, last fault, remote start). Additional profiles will be added as capability documents are collected from more models. See [Contributing](#contributing) if you'd like to help.

## Limitations

- **Only newer "TS" (Thing Shadow) appliances are supported.** These communicate via AWS IoT MQTT. Older appliances using the Whirlpool REST API will not be discovered.
- **No control support.** This integration is read-only (sensors only). It does not support starting, stopping, or changing cycles remotely.
- **Cloud-dependent.** Requires an active internet connection and access to the Whirlpool cloud API.
- **No EU region support.** Currently only the US (NAR) region is supported.
- **Credentials are stored in HA config.** Your Whirlpool account email and password are stored in the Home Assistant config entry. Use a strong, unique password.

## How It Works

The integration authenticates through a multi-step chain:

1. **OAuth** — Email/password login to the Whirlpool cloud API using brand-specific app credentials
2. **Cognito Identity** — Exchanges the OAuth token for an AWS Cognito identity
3. **AWS Credentials** — Obtains temporary AWS credentials via Cognito (refreshed automatically before expiry)
4. **AWS IoT MQTT** — Connects to the MQTT broker and subscribes to appliance state topics

State updates are pushed in real-time over MQTT. A polling fallback runs every 30 seconds to catch any missed updates. AWS credentials are proactively refreshed 10 minutes before expiry to maintain a stable connection.

On first connect, the integration loads a **capability profile** for your appliance model. The profile is sourced from the AWS IoT capability document (bundled for known models) and defines the exact set of cycles, options, and valid values your appliance supports. This drives both sensor creation and the valid values lists that Home Assistant uses for enum validation.

## Contributing

The easiest way to expand model support is to capture and share your appliance's capability document. Capability document research and the fixture capture tooling were developed by [Paul T. (pts211)](https://github.com/pts211/ha-whirlpool-aws).

To capture fixtures for your appliance:

```bash
python3 -m venv /tmp/capture-venv && \
source /tmp/capture-venv/bin/activate && \
pip install -q "paho-mqtt>=2.0.0" git+https://github.com/pts211/whirlpool-sixth-sense.git@aws_iot-scaffolding && \
curl -sO https://raw.githubusercontent.com/pts211/whirlpool-sixth-sense/aws_iot-scaffolding/tools/capture_fixtures.py && \
python capture_fixtures.py \
  --email you@example.com \
  --password 'yourpass' \
  --brand Maytag \
  --region US \
  --all \
  --redact \
  --output-dir ~/Desktop/fixtures && \
deactivate && rm -rf /tmp/capture-venv capture_fixtures.py
```

The `--redact` flag scrubs all device identifiers before writing. Zip the `fixtures/` folder and open an issue or pull request.

## Credits

- [Paul T. (pts211)](https://github.com/pts211/ha-whirlpool-aws) for capability document research, the appliance profile concept, and fixture capture tooling
- [abmantis/whirlpool-sixth-sense](https://github.com/abmantis/whirlpool-sixth-sense) for original Whirlpool OAuth reverse engineering

## Disclaimer

This is an unofficial integration. It is not affiliated with, endorsed by, or supported by Maytag, Whirlpool, or KitchenAid. Use at your own risk.
