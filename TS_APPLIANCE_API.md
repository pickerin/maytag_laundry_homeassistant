# Whirlpool TS (Thing Shadow) Appliance API

Reverse-engineered from the Maytag Android app (com.maytag.android.mtapp v5.9.0) to support newer Whirlpool/Maytag/KitchenAid appliances that use AWS IoT instead of the legacy REST API.

## Background

Newer Whirlpool-family appliances are registered as "tsAppliance" (Thing Shadow) devices rather than "legacyAppliance" devices. These devices:

- Appear in the OAuth JWT under `TS_SAID` (not `SAID`)
- Return empty arrays from the v3 appliance list endpoint (`/api/v3/appliance/all/account/{accountId}`)
- Cannot be accessed via the legacy REST endpoints (`/api/v1/appliance/{said}` returns 401)
- Use AWS IoT Core MQTT for all communication

## Authentication Chain

TS appliance access requires a 3-step authentication flow:

### Step 1: OAuth Login (existing)

Standard OAuth password grant — unchanged from the current library.

```
POST https://api.whrcloud.com/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=password&username={email}&password={password}&client_id={client_id}&client_secret={client_secret}
```

The response JWT contains:
- `TS_SAID`: array of TS device SAIDs (e.g., `["WPR4BV39NFM8D", "WPR4VYY9JV8E7"]`)
- `SAID`: array of legacy device SAIDs (empty for TS-only accounts)
- `accountId`: account identifier

### Step 2: Cognito Identity Exchange

Exchange the OAuth Bearer token for an AWS Cognito identity.

```
GET https://api.whrcloud.com/api/v1/cognito/identityid
Authorization: Bearer {access_token}
```

Response:
```json
{
  "identityId": "us-east-2:8a99e100-c1b7-c001-a432-e5bbc144addc",
  "token": "eyJraWQiOi..."
}
```

### Step 3: AWS Credentials via Cognito

Exchange the Cognito identity for temporary AWS credentials.

```
POST https://cognito-identity.us-east-2.amazonaws.com/
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSCognitoIdentityService.GetCredentialsForIdentity

{
  "IdentityId": "{identityId from step 2}",
  "Logins": {
    "cognito-identity.amazonaws.com": "{token from step 2}"
  }
}
```

Response:
```json
{
  "Credentials": {
    "AccessKeyId": "ASIA...",
    "SecretKey": "...",
    "SessionToken": "...",
    "Expiration": 1775399097.0
  },
  "IdentityId": "us-east-2:..."
}
```

These temporary AWS credentials are used for both the IoT MQTT connection and the `describe_thing` API call.

## AWS Configuration

| Parameter | Value |
|-----------|-------|
| AWS Region | `us-east-2` |
| Cognito Identity Pool ID | `us-east-2:7b9116c3-b3b5-427e-8629-afbf3744f223` |
| IoT MQTT Endpoint | `wt.applianceconnect.net` |
| IoT MQTT Port | 443 (WSS) |
| AWS Account ID | `595287146689` |
| IAM Role | `iot-cf-nar-identity-pool-auth-role` |

For EMEA devices:
| Parameter | Value |
|-----------|-------|
| AWS Region | `eu-central-1` |
| IoT MQTT Endpoint | `wt-eu.applianceconnect.net` |

## Device Discovery

TS devices are discovered by decoding the JWT from Step 1 to extract the `TS_SAID` array. Device metadata is then retrieved via the AWS IoT `DescribeThing` API:

```python
import boto3

iot = boto3.client("iot", region_name="us-east-2",
                   aws_access_key_id=access_key,
                   aws_secret_access_key=secret_key,
                   aws_session_token=session_token)

result = iot.describe_thing(thingName="WPR4BV39NFM8D")
```

Response includes:
```json
{
  "thingName": "WPR4BV39NFM8D",
  "thingTypeName": "MTW7205RR0",
  "attributes": {
    "Brand": "MAYTAG",
    "CapabilityPartNumber": "W11771387",
    "Category": "LAUNDRY",
    "CreatedDate": "2025-11-30_16:17:40",
    "Name": "4d617974616720576173686572",
    "Serial": "CE3600456",
    "UserId": "us-east-2:8a99e100-c1b7-c001-a432-e5bbc144addc",
    "WifiMacAddress": "3C:8A:1F:0C:7D:50"
  }
}
```

Key fields:
- `thingTypeName` — the model prefix used in MQTT topics (e.g., `MTW7205RR0`)
- `attributes.Name` — hex-encoded friendly name (decode as UTF-8: `4d617974616720576173686572` = "Maytag Washer")
- `attributes.Category` — device category (e.g., `LAUNDRY`)
- `attributes.Brand` — brand name
- `attributes.CapabilityPartNumber` — used for capability file downloads

## MQTT Communication

### Connection

Connect to `wt.applianceconnect.net:443` using MQTT over WebSocket with AWS SigV4 signing. The `awscrt` Python library handles this:

```python
from awsiot import mqtt_connection_builder
from awscrt import auth as awsauth

credentials_provider = awsauth.AwsCredentialsProvider.new_static(
    access_key_id=access_key,
    secret_access_key=secret_key,
    session_token=session_token,
)

mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
    endpoint="wt.applianceconnect.net",
    region="us-east-2",
    credentials_provider=credentials_provider,
    client_id="my-client-id",
)
mqtt_connection.connect().result(timeout=15)
```

### MQTT Topic Structure

All topics use the pattern: `{prefix}/{thingTypeName}/{said}/{suffix}`

Where `{thingTypeName}` comes from `describe_thing` (e.g., `MTW7205RR0`).

| Purpose | Topic | Direction |
|---------|-------|-----------|
| State updates (push) | `dt/{model}/{said}/state/update` | Subscribe |
| Command responses | `cmd/{model}/{said}/response/{cognitoIdentityId}` | Subscribe |
| Send commands | `cmd/{model}/{said}/request/{cognitoIdentityId}` | Publish |
| Presence connected | `$aws/events/presence/connected/{said}` | Subscribe |
| Presence disconnected | `$aws/events/presence/disconnected/{said}` | Subscribe |
| Capability download | `api/capability/download/{model}/{said}/response` | Subscribe |
| OTA status | `dt/{model}/{said}/ota/status` | Subscribe |

### Requesting Appliance State

Publish a `getState` command to receive the full appliance state:

```
Topic: cmd/{thingTypeName}/{said}/request/{cognitoIdentityId}

Payload:
{
  "requestId": "<uuid>",
  "timestamp": <epoch_ms>,
  "payload": {
    "addressee": "appliance",
    "command": "getState"
  }
}
```

### Example State Responses

**Washer:**
```json
{
  "requestId": "c1f08369-e2f9-43e1-a1c2-ef7d8d5ab013",
  "response": "accepted",
  "payload": {
    "washer": {
      "applianceState": "running",
      "cycleName": "cleanWasher",
      "cycleType": "standard",
      "specialName": "",
      "currentPhase": "rinse",
      "cycleTime": {
        "state": "running",
        "time": 3665,
        "timeComplete": 1775397826,
        "timePaused": 1775394975
      },
      "delayTime": {
        "state": "idle",
        "time": 0,
        "timeComplete": 0,
        "timePaused": 0
      },
      "sessionId": "50fb9c3e-8231-4edf-92ce-69fb893558b5",
      "cleanWasher": false,
      "doorStatus": "closed",
      "doorLockStatus": true
    },
    "remoteStartEnable": false,
    "faultHistory": ["F0E3", "F8E6", "F0E5", "none", "none"],
    "activeFault": "none",
    "faucet": {
      "faucetState": "FAUCET_IDLE",
      "soakDuration": {"timeComplete": 1775396458}
    },
    "sound": {"cycleSignal": "max"},
    "capabilityPartNumber": "W11771387",
    "systemVersion": "0.0.0"
  }
}
```

**Dryer:**
```json
{
  "requestId": "49e40428-8d85-4152-b541-097398814b34",
  "response": "accepted",
  "payload": {
    "dryer": {
      "applianceState": "running",
      "cycleName": "steamRefresh",
      "cycleType": "standard",
      "specialName": "",
      "currentPhase": "dry",
      "dryTemperature": "high",
      "wrinkleShield": "off",
      "staticGuardEnable": "off",
      "steam": "off",
      "extraPower": "off",
      "pets": "off",
      "cycleTime": {
        "state": "running",
        "time": 1215,
        "timeComplete": 1775395276,
        "timePaused": 1775394350
      },
      "sessionId": "9fce9493-c5e8-4d98-b09e-09b2e1f8bd6d",
      "lowAirFlow": false,
      "lintTrap": false,
      "drumLight": false,
      "doorStatus": "closed"
    },
    "remoteStartEnable": false,
    "hmiControlLockout": false,
    "faultHistory": ["none", "none", "none", "none", "none"],
    "activeFault": "none",
    "sound": {"cycleSignal": "max"},
    "capabilityPartNumber": "W11771436",
    "systemVersion": "0.0.0"
  }
}
```

## IAM Policy Observations

The Cognito-issued credentials (`iot-cf-nar-identity-pool-auth-role`) have limited permissions:

**Allowed:**
- `iot:Connect` — MQTT WebSocket connection
- `iot:Subscribe` — to `dt/{model}/{said}/*`, `cmd/{model}/{said}/response/{identityId}`, presence topics
- `iot:Publish` — to `cmd/{model}/{said}/request/{identityId}`
- `iot:DescribeThing` — get device metadata
- `iot:CreateThingGroup`, `iot:DescribeThingGroup`, `iot:UpdateThingGroup` — user claim flow

**Not allowed:**
- `iot:DescribeEndpoint` — must know `wt.applianceconnect.net` in advance
- `iot:GetThingShadow` via REST — returns 403 (MQTT shadow topics also appear restricted)
- Multi-level wildcard subscriptions (`#`) — triggers disconnect
- Publishing to topics with incorrect model prefix — triggers disconnect

## Encrypted App Configuration (Data.json)

The Maytag app stores its backend configuration in `assets/Data.json` as an encrypted payload. This contains per-region, per-brand, per-environment endpoint configuration including the IoT `customerSpecificEndpoint`.

**Decryption:**
- Algorithm: AES-256-GCM (using first 16 bytes of key)
- IV: 12 zero bytes
- Tag size: 128 bits
- Key derivation: `SHA-512("Smart2000")[:16]`

```python
import hashlib, base64, json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

with open("assets/Data.json") as f:
    data = json.load(f)

key = hashlib.sha512(b"Smart2000").digest()[:16]
ciphertext = base64.b64decode(data["payload"])
plaintext = AESGCM(key).decrypt(bytes(12), ciphertext, None)
config = json.loads(plaintext)
```

**Relevant production endpoints from decrypted config:**

| Region | Brand | IoT Endpoint | Base URL |
|--------|-------|-------------|----------|
| NAR | Maytag | `wt.applianceconnect.net` | `https://api.whrcloud.com/` |
| NAR | Whirlpool | `wt.applianceconnect.net` | `https://api.whrcloud.com/` |
| NAR | KitchenAid | `wt.applianceconnect.net` | `https://api.whrcloud.com/` |
| EMEA | Whirlpool | `wt-eu.applianceconnect.net` | `https://prod-api.whrcloud.eu/` |
| EMEA | KitchenAid | `wt-eu.applianceconnect.net` | `https://api.whrcloud.eu/` |
| EMEA | Hotpoint | `wt-eu.applianceconnect.net` | `https://api.whrcloud.eu/` |
| EMEA | Bauknecht | `wt-eu.applianceconnect.net` | `https://api.whrcloud.eu/` |

## Summary of Differences from Legacy API

| Aspect | Legacy | TS (Thing Shadow) |
|--------|--------|-------------------|
| JWT field | `SAID` | `TS_SAID` |
| v3 API listing | Populates `legacyAppliance` | Empty `tsAppliance` array |
| Data transport | STOMP WebSocket + REST | AWS IoT MQTT |
| Auth for data | Bearer token | AWS SigV4 (Cognito credentials) |
| Initial state | `GET /api/v1/appliance/{said}` | MQTT `getState` command |
| Real-time updates | STOMP `/topic/{said}` | MQTT `dt/{model}/{said}/state/update` |
| Send commands | `POST /api/v1/appliance/command` | MQTT `cmd/{model}/{said}/request/{id}` |
| Device metadata | From v3 API response | `iot:DescribeThing` |

## Dependencies for Implementation

- `boto3` — AWS SDK for `describe_thing` API
- `awscrt` + `awsiot` — AWS IoT MQTT connection with SigV4 WebSocket signing
- `aiohttp` — async HTTP for OAuth and Cognito identity exchange
