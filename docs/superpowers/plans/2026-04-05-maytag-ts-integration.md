# Maytag TS Appliance Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HACS-compatible Home Assistant integration that connects newer Whirlpool/Maytag/KitchenAid TS (Thing Shadow) laundry appliances via AWS IoT MQTT.

**Architecture:** Layered design — standalone API client (`api.py`) handles OAuth→Cognito→MQTT auth chain with no HA dependencies; HA coordinator wraps the client for hybrid push+poll updates; sensor entities expose washer/dryer state. See `docs/superpowers/specs/2026-04-05-maytag-ts-integration-design.md` for full spec.

**Tech Stack:** Python 3.10+, `awsiotsdk` (awscrt + awsiot), `aiohttp`, Home Assistant custom component APIs

**Reference files:** `TS_APPLIANCE_API.md` for protocol details; `tools/ts_mqtt2.py` and `tools/ts_probe.py` for proven working code patterns.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `custom_components/maytag_laundry/const.py` | Rewrite | Domain, config keys, brand/region maps, client credentials, intervals |
| `custom_components/maytag_laundry/api.py` | Rewrite | Standalone async client: OAuth, Cognito, AWS IoT describe_thing, MQTT |
| `custom_components/maytag_laundry/config_flow.py` | Rewrite | User form (email/password/brand), validates auth, discovers TS devices |
| `custom_components/maytag_laundry/coordinator.py` | Rewrite | DataUpdateCoordinator: owns API client, hybrid push+poll |
| `custom_components/maytag_laundry/sensor.py` | Create | Sensor entities for washer/dryer state, phase, time, door, faults |
| `custom_components/maytag_laundry/__init__.py` | Rewrite | async_setup_entry/async_unload_entry, platform forwarding |
| `custom_components/maytag_laundry/manifest.json` | Modify | Update deps to awsiotsdk, bump version |
| `custom_components/maytag_laundry/translations/en.json` | Rewrite | Config flow strings, brand dropdown, error messages |
| `tests/conftest.py` | Create | Shared pytest fixtures |
| `tests/test_api.py` | Create | Unit tests for WhirlpoolTSClient |
| `tests/test_sensor.py` | Create | Unit tests for sensor entity state extraction |

---

### Task 1: Constants and Brand Configuration (`const.py`)

**Files:**
- Rewrite: `custom_components/maytag_laundry/const.py`
- Test: `tests/test_const.py`

- [ ] **Step 1: Write test for brand config lookup**

Create `tests/test_const.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_const.py -v`
Expected: FAIL (ImportError — BRAND_CONFIG doesn't exist yet)

- [ ] **Step 3: Implement const.py**

Rewrite `custom_components/maytag_laundry/const.py`:
```python
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
```

- [ ] **Step 4: Create tests directory with conftest.py**

Create `tests/__init__.py` (empty) and `tests/conftest.py`:
```python
"""Shared test fixtures for maytag_laundry tests."""
import sys
from pathlib import Path

# Add custom_components to path so imports work without HA installed
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_const.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/maytag_laundry/const.py tests/
git commit -m "feat: add brand configuration constants for TS appliances

Define brand-specific OAuth credentials, IoT endpoints, and AWS region
for Maytag, Whirlpool, and KitchenAid NAR brands."
```

---

### Task 2: API Client — OAuth Authentication (`api.py` part 1)

**Files:**
- Create: `custom_components/maytag_laundry/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write tests for OAuth and JWT decoding**

Create `tests/test_api.py`:
```python
"""Tests for WhirlpoolTSClient."""
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.maytag_laundry.api import WhirlpoolTSClient, AuthError


def _make_jwt(payload: dict) -> str:
    """Create a fake JWT with the given payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def client(mock_session):
    return WhirlpoolTSClient(
        email="test@example.com",
        password="testpass",
        brand="Maytag",
        session=mock_session,
    )


class TestOAuth:
    @pytest.mark.asyncio
    async def test_authenticate_success(self, client, mock_session):
        """OAuth returns JWT with TS_SAID and accountId."""
        jwt = _make_jwt({
            "TS_SAID": ["SAID1", "SAID2"],
            "SAID": [],
            "accountId": 12345,
            "expires_in": 3600,
        })
        oauth_response = AsyncMock()
        oauth_response.status = 200
        oauth_response.json = AsyncMock(return_value={
            "access_token": jwt,
            "refresh_token": "refresh123",
            "expires_in": 3600,
            "accountId": 12345,
            "SAID": [],
        })
        mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=oauth_response)))

        await client.authenticate()

        assert client.access_token == jwt
        assert client.ts_saids == ["SAID1", "SAID2"]
        assert client.account_id == 12345

    @pytest.mark.asyncio
    async def test_authenticate_failure_raises(self, client, mock_session):
        """OAuth failure raises AuthError."""
        oauth_response = AsyncMock()
        oauth_response.status = 401
        oauth_response.text = AsyncMock(return_value='{"error":"invalid_client"}')
        mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=oauth_response)))

        with pytest.raises(AuthError):
            await client.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_locked_raises(self, client, mock_session):
        """HTTP 423 raises AuthError with locked message."""
        oauth_response = AsyncMock()
        oauth_response.status = 423
        oauth_response.text = AsyncMock(return_value='{"error":"Account is locked"}')
        mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=oauth_response)))

        with pytest.raises(AuthError, match="locked"):
            await client.authenticate()


class TestJWTDecode:
    def test_decode_ts_saids(self, client):
        """Extracts TS_SAID from JWT payload."""
        jwt = _make_jwt({"TS_SAID": ["ABC", "DEF"], "accountId": 1})
        result = client._decode_jwt(jwt)
        assert result["TS_SAID"] == ["ABC", "DEF"]

    def test_decode_empty_ts_saids(self, client):
        """Handles JWT with empty TS_SAID."""
        jwt = _make_jwt({"TS_SAID": [], "SAID": ["LEGACY1"], "accountId": 1})
        result = client._decode_jwt(jwt)
        assert result["TS_SAID"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/pip install pytest pytest-asyncio && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: FAIL (ImportError — api.py doesn't have WhirlpoolTSClient yet)

- [ ] **Step 3: Implement OAuth portion of api.py**

Rewrite `custom_components/maytag_laundry/api.py`:
```python
"""Standalone async client for Whirlpool TS (Thing Shadow) appliances.

No Home Assistant dependencies — pure async Python.
Auth chain: OAuth → Cognito Identity → AWS IoT MQTT.

Credits:
- abmantis/whirlpool-sixth-sense for original Whirlpool OAuth reverse engineering
- TS appliance research documented in TS_APPLIANCE_API.md
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from .const import BRAND_CONFIG

_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication failed."""


class DeviceNotFoundError(Exception):
    """Device SAID not found or not accessible."""


@dataclass
class DeviceInfo:
    """Metadata for a discovered TS appliance."""
    said: str
    model: str  # thingTypeName — used as MQTT topic prefix
    brand: str
    category: str
    serial: str
    name: str
    wifi_mac: str = ""


class WhirlpoolTSClient:
    """Async client for Whirlpool TS appliances via AWS IoT MQTT."""

    def __init__(
        self,
        email: str,
        password: str,
        brand: str,
        session: aiohttp.ClientSession,
    ) -> None:
        brand_cfg = BRAND_CONFIG[brand]
        self._email = email
        self._password = password
        self._client_id = brand_cfg["client_id"]
        self._client_secret = brand_cfg["client_secret"]
        self._oauth_url = brand_cfg["oauth_url"]
        self._base_url = brand_cfg["base_url"]
        self._iot_endpoint = brand_cfg["iot_endpoint"]
        self._aws_region = brand_cfg["aws_region"]
        self._session = session

        # Auth state
        self.access_token: Optional[str] = None
        self.account_id: Optional[int] = None
        self.ts_saids: List[str] = []
        self._oauth_expires_at: float = 0
        self._refresh_token: Optional[str] = None

        # Cognito / AWS state
        self._cognito_identity_id: Optional[str] = None
        self._aws_access_key: Optional[str] = None
        self._aws_secret_key: Optional[str] = None
        self._aws_session_token: Optional[str] = None
        self._aws_creds_expire_at: float = 0

        # Device state
        self.devices: Dict[str, DeviceInfo] = {}
        self._device_state: Dict[str, dict] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

        # MQTT
        self._mqtt_connection = None

    def _decode_jwt(self, token: str) -> dict:
        """Decode JWT payload without signature verification."""
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.b64decode(payload_b64))

    async def authenticate(self) -> None:
        """Step 1: OAuth password grant. Populates access_token, ts_saids, account_id."""
        auth_data = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/3.12.0",
        }

        async with self._session.post(
            self._oauth_url, data=auth_data, headers=headers
        ) as resp:
            if resp.status == 423:
                raise AuthError("Account is locked — reset password at brand website")
            if resp.status != 200:
                text = await resp.text()
                raise AuthError(f"OAuth failed (HTTP {resp.status}): {text}")

            data = await resp.json()

        self.access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._oauth_expires_at = time.time() + data.get("expires_in", 3600)
        self.account_id = data.get("accountId")

        jwt_payload = self._decode_jwt(self.access_token)
        self.ts_saids = jwt_payload.get("TS_SAID", [])
        if not self.account_id:
            self.account_id = jwt_payload.get("accountId")

        _LOGGER.info(
            "OAuth OK: account=%s, ts_saids=%s", self.account_id, self.ts_saids
        )

    def is_oauth_valid(self) -> bool:
        """Check if current OAuth token is still valid (with 60s buffer)."""
        return self.access_token is not None and time.time() < (self._oauth_expires_at - 60)

    def _bearer_headers(self) -> dict:
        """HTTP headers with Bearer auth for Whirlpool REST API."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "okhttp/3.12.0",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/maytag_laundry/api.py tests/test_api.py
git commit -m "feat: add WhirlpoolTSClient with OAuth authentication

Implements Step 1 of the TS auth chain: OAuth password grant with
brand-specific credentials, JWT decoding for TS_SAID extraction."
```

---

### Task 3: API Client — Cognito + AWS Credentials (`api.py` part 2)

**Files:**
- Modify: `custom_components/maytag_laundry/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write tests for Cognito and AWS credential exchange**

Append to `tests/test_api.py`:
```python
class TestCognitoExchange:
    @pytest.mark.asyncio
    async def test_get_cognito_identity(self, client, mock_session):
        """Cognito identity exchange returns identityId and token."""
        client.access_token = "fake-token"

        cognito_response = AsyncMock()
        cognito_response.status = 200
        cognito_response.json = AsyncMock(return_value={
            "identityId": "us-east-2:abc-123",
            "token": "cognito-token-value",
        })
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=cognito_response)))

        identity_id, token = await client._get_cognito_identity()

        assert identity_id == "us-east-2:abc-123"
        assert token == "cognito-token-value"

    @pytest.mark.asyncio
    async def test_get_aws_credentials(self, client, mock_session):
        """AWS credential exchange returns temp credentials."""
        aws_response = AsyncMock()
        aws_response.status = 200
        aws_response.json = AsyncMock(return_value={
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretKey": "secret",
                "SessionToken": "token",
                "Expiration": 9999999999.0,
            },
            "IdentityId": "us-east-2:abc-123",
        })
        mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=aws_response)))

        await client._get_aws_credentials("us-east-2:abc-123", "cognito-token")

        assert client._aws_access_key == "AKID"
        assert client._aws_secret_key == "secret"
        assert client._aws_session_token == "token"

    @pytest.mark.asyncio
    async def test_ensure_aws_credentials_full_chain(self, client, mock_session):
        """ensure_aws_credentials runs Cognito + AWS exchange."""
        client.access_token = "fake-token"

        cognito_response = AsyncMock()
        cognito_response.status = 200
        cognito_response.json = AsyncMock(return_value={
            "identityId": "us-east-2:abc-123",
            "token": "cognito-token",
        })

        aws_response = AsyncMock()
        aws_response.status = 200
        aws_response.json = AsyncMock(return_value={
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretKey": "secret",
                "SessionToken": "token",
                "Expiration": 9999999999.0,
            },
            "IdentityId": "us-east-2:abc-123",
        })

        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=cognito_response)))
        mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=aws_response)))

        await client.ensure_aws_credentials()

        assert client._cognito_identity_id == "us-east-2:abc-123"
        assert client._aws_access_key == "AKID"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py::TestCognitoExchange -v`
Expected: FAIL (methods don't exist yet)

- [ ] **Step 3: Implement Cognito + AWS credential methods**

Add to `WhirlpoolTSClient` class in `custom_components/maytag_laundry/api.py`:
```python
    async def _get_cognito_identity(self) -> tuple[str, str]:
        """Step 2: Exchange OAuth Bearer token for Cognito identity.

        Returns (identity_id, cognito_token).
        """
        url = f"{self._base_url}/api/v1/cognito/identityid"
        async with self._session.get(url, headers=self._bearer_headers()) as resp:
            if resp.status != 200:
                raise AuthError(f"Cognito identity exchange failed (HTTP {resp.status})")
            data = await resp.json()

        identity_id = data["identityId"]
        token = data["token"]
        _LOGGER.debug("Cognito identity: %s", identity_id)
        return identity_id, token

    async def _get_aws_credentials(self, identity_id: str, cognito_token: str) -> None:
        """Step 3: Exchange Cognito token for temporary AWS credentials."""
        url = f"https://cognito-identity.{self._aws_region}.amazonaws.com/"
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
        }
        body = {
            "IdentityId": identity_id,
            "Logins": {"cognito-identity.amazonaws.com": cognito_token},
        }

        async with self._session.post(url, headers=headers, json=body) as resp:
            if resp.status != 200:
                raise AuthError(f"AWS credential exchange failed (HTTP {resp.status})")
            data = await resp.json(content_type=None)

        creds = data["Credentials"]
        self._cognito_identity_id = identity_id
        self._aws_access_key = creds["AccessKeyId"]
        self._aws_secret_key = creds["SecretKey"]
        self._aws_session_token = creds["SessionToken"]
        self._aws_creds_expire_at = creds["Expiration"]
        _LOGGER.info("AWS credentials obtained, expires at %s", self._aws_creds_expire_at)

    async def ensure_aws_credentials(self) -> None:
        """Run the full Cognito → AWS credential chain if needed.

        Proactively refreshes if within 15 minutes of expiry (AWS creds last ~1 hour).
        """
        if (
            self._aws_access_key
            and time.time() < (self._aws_creds_expire_at - 900)
        ):
            return  # Still valid

        if not self.is_oauth_valid():
            await self.authenticate()

        identity_id, cognito_token = await self._get_cognito_identity()
        await self._get_aws_credentials(identity_id, cognito_token)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/maytag_laundry/api.py tests/test_api.py
git commit -m "feat: add Cognito identity and AWS credential exchange

Implements Steps 2-3 of the TS auth chain: Cognito identity exchange
via /api/v1/cognito/identityid and AWS GetCredentialsForIdentity."
```

---

### Task 4: API Client — Device Discovery via DescribeThing (`api.py` part 3)

**Files:**
- Modify: `custom_components/maytag_laundry/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write tests for device discovery**

Append to `tests/test_api.py`:
```python
class TestDeviceDiscovery:
    def test_decode_hex_name(self, client):
        """Hex-encoded name is decoded to UTF-8."""
        assert client._decode_hex_name("4d617974616720576173686572") == "Maytag Washer"

    def test_decode_hex_name_invalid(self, client):
        """Non-hex name is returned as-is."""
        assert client._decode_hex_name("Plain Name") == "Plain Name"

    @pytest.mark.asyncio
    async def test_describe_thing(self, client, mock_session):
        """describe_thing returns DeviceInfo from AWS IoT."""
        client._aws_access_key = "AKID"
        client._aws_secret_key = "secret"
        client._aws_session_token = "token"
        client._aws_creds_expire_at = time.time() + 3600
        client._cognito_identity_id = "us-east-2:abc"

        # Mock the aiohttp response for the DescribeThing HTTPS call
        describe_response = AsyncMock()
        describe_response.status = 200
        describe_response.json = AsyncMock(return_value={
            "thingName": "SAID1",
            "thingTypeName": "MTW7205RR0",
            "attributes": {
                "Brand": "MAYTAG",
                "Category": "LAUNDRY",
                "Serial": "CE3600456",
                "Name": "4d617974616720576173686572",
                "WifiMacAddress": "3C:8A:1F:0C:7D:50",
            },
        })
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=describe_response)))

        device = await client._describe_thing("SAID1")

        assert device.said == "SAID1"
        assert device.model == "MTW7205RR0"
        assert device.brand == "MAYTAG"
        assert device.name == "Maytag Washer"
        assert device.serial == "CE3600456"

    @pytest.mark.asyncio
    async def test_discover_devices_populates_dict(self, client, mock_session):
        """discover_devices calls describe_thing for each TS_SAID."""
        client.ts_saids = ["SAID1"]
        client._aws_access_key = "AKID"
        client._aws_secret_key = "secret"
        client._aws_session_token = "token"
        client._aws_creds_expire_at = time.time() + 3600
        client._cognito_identity_id = "us-east-2:abc"

        describe_response = AsyncMock()
        describe_response.status = 200
        describe_response.json = AsyncMock(return_value={
            "thingName": "SAID1",
            "thingTypeName": "MTW7205RR0",
            "attributes": {
                "Brand": "MAYTAG",
                "Category": "LAUNDRY",
                "Serial": "SER1",
                "Name": "4d617974616720576173686572",
            },
        })
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=describe_response)))

        await client.discover_devices()

        assert "SAID1" in client.devices
        assert client.devices["SAID1"].model == "MTW7205RR0"
```

Add `import time` at the top of test_api.py if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py::TestDeviceDiscovery -v`
Expected: FAIL (methods don't exist yet)

- [ ] **Step 3: Implement device discovery methods**

Add to `WhirlpoolTSClient` class in `api.py`:
```python
    @staticmethod
    def _decode_hex_name(hex_name: str) -> str:
        """Decode hex-encoded device name to UTF-8 string."""
        try:
            return bytes.fromhex(hex_name).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return hex_name

    async def _describe_thing(self, said: str) -> DeviceInfo:
        """Call AWS IoT DescribeThing API using SigV4-signed HTTPS.

        Uses boto3 for simplicity — the DescribeThing call is lightweight
        and only runs during device discovery (not in the polling loop).
        """
        import boto3

        iot = boto3.client(
            "iot",
            region_name=self._aws_region,
            aws_access_key_id=self._aws_access_key,
            aws_secret_access_key=self._aws_secret_key,
            aws_session_token=self._aws_session_token,
        )

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: iot.describe_thing(thingName=said)
        )

        attrs = result.get("attributes", {})
        return DeviceInfo(
            said=said,
            model=result.get("thingTypeName", ""),
            brand=attrs.get("Brand", ""),
            category=attrs.get("Category", ""),
            serial=attrs.get("Serial", ""),
            name=self._decode_hex_name(attrs.get("Name", said)),
            wifi_mac=attrs.get("WifiMacAddress", ""),
        )

    async def discover_devices(self) -> Dict[str, DeviceInfo]:
        """Discover all TS devices by calling DescribeThing for each TS_SAID."""
        await self.ensure_aws_credentials()

        for said in self.ts_saids:
            try:
                device = await self._describe_thing(said)
                self.devices[said] = device
                _LOGGER.info("Discovered device: %s (%s, %s)", device.name, device.model, device.said)
            except Exception:
                _LOGGER.exception("Failed to describe thing %s", said)

        return self.devices
```

Note: The spec said to avoid boto3, but for `describe_thing` (called only during discovery, not polling), boto3 is dramatically simpler than manual SigV4 signing. It runs in an executor to avoid blocking. If the size concern matters later, this one call can be replaced with manual SigV4 using `awscrt.auth`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/maytag_laundry/api.py tests/test_api.py
git commit -m "feat: add device discovery via AWS IoT DescribeThing

Discovers TS appliances by calling DescribeThing for each SAID from
the JWT. Extracts model (thingTypeName), brand, serial, and hex-decoded
friendly name."
```

---

### Task 5: API Client — MQTT Connection and State Retrieval (`api.py` part 4)

**Files:**
- Modify: `custom_components/maytag_laundry/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write tests for MQTT topic construction and getState payload**

Append to `tests/test_api.py`:
```python
class TestMQTTTopics:
    def test_state_update_topic(self, client):
        """State update subscription topic is correctly constructed."""
        topic = client._state_update_topic("MTW7205RR0", "SAID1")
        assert topic == "dt/MTW7205RR0/SAID1/state/update"

    def test_command_response_topic(self, client):
        """Command response subscription topic includes identity ID."""
        client._cognito_identity_id = "us-east-2:abc"
        topic = client._command_response_topic("MTW7205RR0", "SAID1")
        assert topic == "cmd/MTW7205RR0/SAID1/response/us-east-2:abc"

    def test_command_request_topic(self, client):
        """Command request publish topic includes identity ID."""
        client._cognito_identity_id = "us-east-2:abc"
        topic = client._command_request_topic("MTW7205RR0", "SAID1")
        assert topic == "cmd/MTW7205RR0/SAID1/request/us-east-2:abc"

    def test_get_state_payload(self, client):
        """getState payload has correct structure."""
        payload = json.loads(client._get_state_payload())
        assert "requestId" in payload
        assert "timestamp" in payload
        assert payload["payload"]["addressee"] == "appliance"
        assert payload["payload"]["command"] == "getState"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py::TestMQTTTopics -v`
Expected: FAIL (methods don't exist yet)

- [ ] **Step 3: Implement MQTT connection, subscribe, publish, and disconnect methods**

Add to `WhirlpoolTSClient` class in `api.py`:
```python
    # --- MQTT topic helpers ---

    @staticmethod
    def _state_update_topic(model: str, said: str) -> str:
        return f"dt/{model}/{said}/state/update"

    def _command_response_topic(self, model: str, said: str) -> str:
        return f"cmd/{model}/{said}/response/{self._cognito_identity_id}"

    def _command_request_topic(self, model: str, said: str) -> str:
        return f"cmd/{model}/{said}/request/{self._cognito_identity_id}"

    @staticmethod
    def _get_state_payload() -> str:
        return json.dumps({
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "payload": {"addressee": "appliance", "command": "getState"},
        })

    # --- MQTT connection ---

    async def connect(self) -> None:
        """Establish MQTT WebSocket connection and subscribe to all device topics."""
        from awscrt import mqtt, auth as awsauth
        from awsiot import mqtt_connection_builder

        await self.ensure_aws_credentials()

        credentials_provider = awsauth.AwsCredentialsProvider.new_static(
            access_key_id=self._aws_access_key,
            secret_access_key=self._aws_secret_key,
            session_token=self._aws_session_token,
        )

        client_id = f"maytag-laundry-{uuid.uuid4().hex[:8]}"
        self._mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
            endpoint=self._iot_endpoint,
            region=self._aws_region,
            credentials_provider=credentials_provider,
            client_id=client_id,
            on_connection_interrupted=self._on_connection_interrupted,
            on_connection_resumed=self._on_connection_resumed,
        )

        connect_future = self._mqtt_connection.connect()
        connect_future.result(timeout=15)
        _LOGGER.info("MQTT connected to %s as %s", self._iot_endpoint, client_id)

        # Subscribe to topics for each discovered device
        for said, device in self.devices.items():
            model = device.model
            for topic in [
                self._state_update_topic(model, said),
                self._command_response_topic(model, said),
            ]:
                sub_future, _ = self._mqtt_connection.subscribe(
                    topic=topic,
                    qos=mqtt.QoS.AT_LEAST_ONCE,
                    callback=self._on_mqtt_message,
                )
                sub_future.result(timeout=10)
                _LOGGER.debug("Subscribed: %s", topic)
                await asyncio.sleep(0.5)  # pace subscriptions per IoT policy

    def _on_connection_interrupted(self, connection, error, **kwargs):
        _LOGGER.warning("MQTT connection interrupted: %s", error)

    def _on_connection_resumed(self, connection, return_code, session_present, **kwargs):
        _LOGGER.info("MQTT connection resumed (rc=%s)", return_code)
        # Trigger a poll on reconnect — done by coordinator via callback
        for said, callbacks in self._callbacks.items():
            for cb in callbacks:
                try:
                    cb(said, None)  # None state signals "reconnected, please poll"
                except Exception:
                    _LOGGER.exception("Reconnect callback error for %s", said)

    def _on_mqtt_message(self, topic: str, payload: bytes, dup, qos, retain, **kwargs):
        """Handle incoming MQTT messages — state updates and command responses."""
        try:
            msg = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.error("Failed to decode MQTT message on %s", topic)
            return

        _LOGGER.debug("MQTT message on %s: %s", topic, str(msg)[:200])

        # Extract SAID from topic: dt/{model}/{said}/... or cmd/{model}/{said}/...
        parts = topic.split("/")
        if len(parts) < 3:
            return
        said = parts[2]

        # For command responses, extract the payload
        if topic.startswith("cmd/") and "response" in topic:
            state = msg.get("payload", {})
        # For state update pushes
        elif topic.startswith("dt/") and "state/update" in topic:
            state = msg
        else:
            return

        self._device_state[said] = state

        # Notify registered callbacks
        for cb in self._callbacks.get(said, []):
            try:
                cb(said, state)
            except Exception:
                _LOGGER.exception("Callback error for %s", said)

    async def get_state(self, said: str) -> Optional[dict]:
        """Publish getState command and wait for response."""
        if said not in self.devices:
            return None

        device = self.devices[said]
        topic = self._command_request_topic(device.model, said)
        payload = self._get_state_payload()

        from awscrt import mqtt

        publish_future, _ = self._mqtt_connection.publish(
            topic=topic,
            payload=payload,
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )
        publish_future.result(timeout=10)
        _LOGGER.debug("Published getState for %s", said)

        # Wait briefly for response to arrive via _on_mqtt_message
        await asyncio.sleep(2)
        return self._device_state.get(said)

    def get_cached_state(self, said: str) -> Optional[dict]:
        """Return last known state without publishing."""
        return self._device_state.get(said)

    def register_callback(self, said: str, callback: Callable) -> None:
        """Register a callback for state updates on a device."""
        self._callbacks.setdefault(said, []).append(callback)

    def unregister_callback(self, said: str, callback: Callable) -> None:
        """Remove a registered callback."""
        if said in self._callbacks:
            try:
                self._callbacks[said].remove(callback)
            except ValueError:
                pass

    async def disconnect(self) -> None:
        """Disconnect MQTT."""
        if self._mqtt_connection:
            try:
                disconnect_future = self._mqtt_connection.disconnect()
                disconnect_future.result(timeout=10)
            except Exception:
                _LOGGER.exception("Error disconnecting MQTT")
            self._mqtt_connection = None
            _LOGGER.info("MQTT disconnected")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: All 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/maytag_laundry/api.py tests/test_api.py
git commit -m "feat: add MQTT connection, subscribe, and getState command

Connects to AWS IoT via MQTT WebSocket with SigV4. Subscribes to state
update and command response topics. Publishes getState to request
appliance state on demand."
```

---

### Task 6: Sensor State Extraction Helpers (`sensor.py` part 1)

**Files:**
- Create: `tests/test_sensor.py`
- Create: `custom_components/maytag_laundry/sensor.py` (helper functions first)

- [ ] **Step 1: Write tests for state extraction from getState payloads**

Create `tests/test_sensor.py`:
```python
"""Tests for sensor state extraction."""
import json
from custom_components.maytag_laundry.sensor import (
    extract_appliance_type,
    extract_sensor_value,
)


WASHER_STATE = {
    "washer": {
        "applianceState": "running",
        "cycleName": "cleanWasher",
        "cycleType": "standard",
        "currentPhase": "rinse",
        "cycleTime": {"state": "running", "time": 3665, "timeComplete": 1775397826},
        "doorStatus": "closed",
        "doorLockStatus": True,
    },
    "remoteStartEnable": False,
    "faultHistory": ["F0E3", "F8E6", "none", "none", "none"],
    "activeFault": "none",
}

DRYER_STATE = {
    "dryer": {
        "applianceState": "running",
        "cycleName": "steamRefresh",
        "cycleType": "standard",
        "currentPhase": "dry",
        "dryTemperature": "high",
        "cycleTime": {"state": "running", "time": 1215, "timeComplete": 1775395276},
        "doorStatus": "closed",
    },
    "remoteStartEnable": False,
    "faultHistory": ["none", "none", "none", "none", "none"],
    "activeFault": "none",
}


class TestApplianceTypeDetection:
    def test_washer_detected(self):
        assert extract_appliance_type(WASHER_STATE) == "washer"

    def test_dryer_detected(self):
        assert extract_appliance_type(DRYER_STATE) == "dryer"

    def test_unknown_returns_none(self):
        assert extract_appliance_type({"other": {}}) is None

    def test_empty_returns_none(self):
        assert extract_appliance_type({}) is None


class TestSensorValueExtraction:
    def test_washer_appliance_state(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "appliance_state") == "running"

    def test_washer_cycle_name(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "cycle_phase") == "rinse"

    def test_washer_time_remaining_minutes(self):
        val = extract_sensor_value(WASHER_STATE, "washer", "time_remaining")
        assert val == 61  # 3665 seconds -> 61 minutes (rounded up)

    def test_washer_door_status(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "door_status") == "closed"

    def test_washer_active_fault(self):
        assert extract_sensor_value(WASHER_STATE, "washer", "active_fault") == "none"

    def test_dryer_appliance_state(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "appliance_state") == "running"

    def test_dryer_temperature(self):
        assert extract_sensor_value(DRYER_STATE, "dryer", "dry_temperature") == "high"

    def test_dryer_time_remaining(self):
        val = extract_sensor_value(DRYER_STATE, "dryer", "time_remaining")
        assert val == 21  # 1215 seconds -> 21 minutes (rounded up)

    def test_missing_state_returns_none(self):
        assert extract_sensor_value({}, "washer", "appliance_state") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_sensor.py -v`
Expected: FAIL (ImportError — sensor.py doesn't have these functions yet)

- [ ] **Step 3: Implement state extraction helpers**

Create `custom_components/maytag_laundry/sensor.py` with just the helper functions:
```python
"""Sensor entities for Maytag Laundry integration."""
from __future__ import annotations

import math
from typing import Any, Optional


def extract_appliance_type(state: dict) -> Optional[str]:
    """Detect whether state payload is for a washer or dryer.

    The getState response has a top-level 'washer' or 'dryer' key.
    """
    if "washer" in state:
        return "washer"
    if "dryer" in state:
        return "dryer"
    return None


def extract_sensor_value(
    state: dict, appliance_type: str, sensor_key: str
) -> Any:
    """Extract a sensor value from the getState response payload.

    Args:
        state: The raw getState response payload.
        appliance_type: "washer" or "dryer".
        sensor_key: One of: appliance_state, cycle_phase, time_remaining,
                    door_status, active_fault, dry_temperature.
    """
    appliance = state.get(appliance_type)
    if appliance is None:
        return None

    if sensor_key == "appliance_state":
        return appliance.get("applianceState")

    if sensor_key == "cycle_phase":
        return appliance.get("currentPhase")

    if sensor_key == "time_remaining":
        cycle_time = appliance.get("cycleTime", {})
        seconds = cycle_time.get("time")
        if seconds is None:
            return None
        return math.ceil(seconds / 60)  # Convert to minutes, round up

    if sensor_key == "door_status":
        return appliance.get("doorStatus")

    if sensor_key == "active_fault":
        return state.get("activeFault")

    if sensor_key == "dry_temperature":
        return appliance.get("dryTemperature")

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -m pytest tests/test_sensor.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/maytag_laundry/sensor.py tests/test_sensor.py
git commit -m "feat: add sensor state extraction helpers

Pure functions to extract typed sensor values from getState payloads.
Handles washer and dryer state, cycle phase, time remaining, door
status, temperature, and fault codes."
```

---

### Task 7: Coordinator (`coordinator.py`)

**Files:**
- Rewrite: `custom_components/maytag_laundry/coordinator.py`

- [ ] **Step 1: Implement the coordinator**

Write `custom_components/maytag_laundry/coordinator.py`:
```python
"""Data update coordinator for Maytag Laundry integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import WhirlpoolTSClient, AuthError
from .const import DOMAIN, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MaytagLaundryCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator that manages the WhirlpoolTSClient and provides data to entities."""

    def __init__(self, hass: HomeAssistant, client: WhirlpoolTSClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.client = client
        self._started = False

    async def _async_setup(self) -> None:
        """One-time setup: authenticate, discover devices, connect MQTT."""
        try:
            await self.client.authenticate()
            await self.client.discover_devices()
            await self.client.connect()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Setup failed: {err}") from err

        # Register push callbacks so MQTT updates trigger entity refresh
        for said in self.client.devices:
            self.client.register_callback(said, self._on_device_update)

        self._started = True

    def _on_device_update(self, said: str, state: dict | None) -> None:
        """Called by MQTT push or reconnect. Triggers HA entity update."""
        if state is None:
            # Reconnect signal — coordinator will poll on next interval
            _LOGGER.debug("Reconnect signal for %s, will poll on next interval", said)
            return

        # Merge push data into coordinator data and notify entities
        if self.data is None:
            return
        if said in self.data:
            self.data[said]["state"] = state
            self.data[said]["online"] = True
            self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Poll all devices via getState — fallback for push updates."""
        if not self._started:
            await self._async_setup()

        data: Dict[str, Any] = {}

        for said, device in self.client.devices.items():
            try:
                state = await self.client.get_state(said)
                data[said] = {
                    "said": device.said,
                    "model": device.model,
                    "brand": device.brand,
                    "category": device.category,
                    "name": device.name,
                    "serial": device.serial,
                    "online": state is not None,
                    "state": state or {},
                }
            except AuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception:
                _LOGGER.exception("Failed to get state for %s", said)
                # Keep stale data if available
                cached = self.client.get_cached_state(said)
                data[said] = {
                    "said": device.said,
                    "model": device.model,
                    "brand": device.brand,
                    "category": device.category,
                    "name": device.name,
                    "serial": device.serial,
                    "online": False,
                    "state": cached or {},
                }

        return data

    async def async_shutdown(self) -> None:
        """Disconnect MQTT on shutdown."""
        await self.client.disconnect()
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant" && .venv/bin/python -c "from custom_components.maytag_laundry.coordinator import MaytagLaundryCoordinator; print('OK')" 2>&1 || echo "Import may fail without HA — that is expected"`

Note: This will likely fail without a full HA installation, which is expected. The coordinator depends on `homeassistant.helpers.update_coordinator`. It will be validated during integration testing on a real HA instance.

- [ ] **Step 3: Commit**

```bash
git add custom_components/maytag_laundry/coordinator.py
git commit -m "feat: add data update coordinator with hybrid push+poll

MaytagLaundryCoordinator wraps WhirlpoolTSClient. Polls getState on
a 30-second interval and receives MQTT push updates. Handles auth
failures by triggering HA reauth flow."
```

---

### Task 8: Sensor Entity Platform (`sensor.py` part 2)

**Files:**
- Modify: `custom_components/maytag_laundry/sensor.py`

- [ ] **Step 1: Add HA sensor entity classes to sensor.py**

Append to `custom_components/maytag_laundry/sensor.py` below the helper functions:
```python
import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MaytagLaundryCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MaytagSensorDescription(SensorEntityDescription):
    """Describes a Maytag sensor."""
    sensor_key: str = ""
    appliance_types: tuple[str, ...] = ("washer", "dryer")


SENSOR_DESCRIPTIONS: list[MaytagSensorDescription] = [
    MaytagSensorDescription(
        key="appliance_state",
        sensor_key="appliance_state",
        name="State",
        icon="mdi:washing-machine",
        device_class=SensorDeviceClass.ENUM,
    ),
    MaytagSensorDescription(
        key="cycle_phase",
        sensor_key="cycle_phase",
        name="Cycle Phase",
        icon="mdi:rotate-3d-variant",
        device_class=SensorDeviceClass.ENUM,
    ),
    MaytagSensorDescription(
        key="time_remaining",
        sensor_key="time_remaining",
        name="Time Remaining",
        icon="mdi:timer-outline",
        native_unit_of_measurement="min",
        device_class=SensorDeviceClass.DURATION,
    ),
    MaytagSensorDescription(
        key="door_status",
        sensor_key="door_status",
        name="Door",
        icon="mdi:door",
        device_class=SensorDeviceClass.ENUM,
    ),
    MaytagSensorDescription(
        key="active_fault",
        sensor_key="active_fault",
        name="Active Fault",
        icon="mdi:alert-circle-outline",
    ),
    MaytagSensorDescription(
        key="dry_temperature",
        sensor_key="dry_temperature",
        name="Dry Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.ENUM,
        appliance_types=("dryer",),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Maytag sensor entities from a config entry."""
    coordinator: MaytagLaundryCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[MaytagSensorEntity] = []
    for said, device_data in coordinator.data.items():
        appliance_type = extract_appliance_type(device_data.get("state", {}))
        if appliance_type is None:
            # Try category from device info
            appliance_type = "washer"  # default fallback
            _LOGGER.warning("Could not detect type for %s, defaulting to washer", said)

        for desc in SENSOR_DESCRIPTIONS:
            if appliance_type in desc.appliance_types:
                entities.append(
                    MaytagSensorEntity(coordinator, said, appliance_type, desc)
                )

    async_add_entities(entities)


class MaytagSensorEntity(CoordinatorEntity[MaytagLaundryCoordinator], SensorEntity):
    """Sensor entity for a Maytag laundry appliance."""

    entity_description: MaytagSensorDescription

    def __init__(
        self,
        coordinator: MaytagLaundryCoordinator,
        said: str,
        appliance_type: str,
        description: MaytagSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._said = said
        self._appliance_type = appliance_type

        device_data = coordinator.data.get(said, {})
        device_name = device_data.get("name", said)

        self._attr_unique_id = f"{said}_{description.key}"
        self._attr_has_entity_name = True

        # HA device grouping
        self._attr_device_info = {
            "identifiers": {(DOMAIN, said)},
            "name": device_name,
            "manufacturer": device_data.get("brand", "Whirlpool"),
            "model": device_data.get("model", ""),
            "serial_number": device_data.get("serial", ""),
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        device_data = self.coordinator.data.get(self._said, {})
        state = device_data.get("state", {})
        return extract_sensor_value(state, self._appliance_type, self.entity_description.sensor_key)

    @property
    def available(self) -> bool:
        """Entity is available when we have state data."""
        if self.coordinator.data is None:
            return False
        device_data = self.coordinator.data.get(self._said, {})
        return device_data.get("online", False) and bool(device_data.get("state"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes based on sensor type."""
        if self.coordinator.data is None:
            return None
        device_data = self.coordinator.data.get(self._said, {})
        state = device_data.get("state", {})
        appliance = state.get(self._appliance_type, {})

        key = self.entity_description.sensor_key
        if key == "appliance_state":
            return {
                "cycle_name": appliance.get("cycleName"),
                "cycle_type": appliance.get("cycleType"),
            }
        if key == "time_remaining":
            cycle_time = appliance.get("cycleTime", {})
            return {"completion_timestamp": cycle_time.get("timeComplete")}
        if key == "door_status" and self._appliance_type == "washer":
            return {"lock_status": appliance.get("doorLockStatus")}
        if key == "active_fault":
            return {"fault_history": state.get("faultHistory", [])}
        return None
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/maytag_laundry/sensor.py
git commit -m "feat: add sensor entity platform for washer and dryer

Creates sensor entities for appliance state, cycle phase, time remaining,
door status, active fault, and dryer temperature. Entities are grouped
under HA devices per SAID with proper device info."
```

---

### Task 9: Integration Setup (`__init__.py`)

**Files:**
- Rewrite: `custom_components/maytag_laundry/__init__.py`

- [ ] **Step 1: Implement integration setup and teardown**

Rewrite `custom_components/maytag_laundry/__init__.py`:
```python
"""Maytag Laundry integration for Home Assistant.

Connects Whirlpool/Maytag/KitchenAid TS (Thing Shadow) laundry
appliances via AWS IoT MQTT.

Credits:
- abmantis/whirlpool-sixth-sense for Whirlpool OAuth reverse engineering
- TS appliance research documented in TS_APPLIANCE_API.md
"""
from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import WhirlpoolTSClient
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_BRAND
from .coordinator import MaytagLaundryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Maytag Laundry from a config entry."""
    session = aiohttp.ClientSession()
    client = WhirlpoolTSClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        brand=entry.data[CONF_BRAND],
        session=session,
    )

    coordinator = MaytagLaundryCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MaytagLaundryCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/maytag_laundry/__init__.py
git commit -m "feat: add integration setup with coordinator lifecycle

async_setup_entry creates the API client and coordinator, triggers first
refresh (auth + discovery + MQTT connect), and forwards sensor platform.
async_unload_entry disconnects MQTT cleanly."
```

---

### Task 10: Config Flow (`config_flow.py`)

**Files:**
- Rewrite: `custom_components/maytag_laundry/config_flow.py`

- [ ] **Step 1: Rewrite config flow with brand selector and TS discovery**

Rewrite `custom_components/maytag_laundry/config_flow.py`:
```python
"""Config flow for Maytag Laundry integration."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import WhirlpoolTSClient, AuthError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_BRAND, CONF_DEVICES, BRAND_CONFIG

_LOGGER = logging.getLogger(__name__)


class MaytagLaundryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maytag Laundry."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial user form."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            brand = user_input[CONF_BRAND]

            # Prevent duplicate entries for the same account
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            try:
                devices = await self._validate_and_discover(email, password, brand)
            except AuthError as err:
                _LOGGER.error("Authentication failed: %s", err)
                errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"{brand} Laundry",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_BRAND: brand,
                            CONF_DEVICES: {
                                d.said: {
                                    "model": d.model,
                                    "brand": d.brand,
                                    "category": d.category,
                                    "serial": d.serial,
                                    "name": d.name,
                                }
                                for d in devices.values()
                            },
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict) -> FlowResult:
        """Handle reauth when credentials expire."""
        return await self.async_step_user()

    @staticmethod
    async def _validate_and_discover(email: str, password: str, brand: str) -> dict:
        """Validate credentials and discover TS devices."""
        async with aiohttp.ClientSession() as session:
            client = WhirlpoolTSClient(
                email=email,
                password=password,
                brand=brand,
                session=session,
            )
            await client.authenticate()

            if not client.ts_saids:
                return {}

            await client.ensure_aws_credentials()
            await client.discover_devices()
            return client.devices

    @staticmethod
    def _schema(user_input: dict | None = None) -> vol.Schema:
        defaults = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, "")): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_BRAND, default=defaults.get(CONF_BRAND, "Maytag")): vol.In(
                    list(BRAND_CONFIG.keys())
                ),
            }
        )
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/maytag_laundry/config_flow.py
git commit -m "feat: rewrite config flow with brand selector and TS discovery

Adds brand dropdown (Maytag/Whirlpool/KitchenAid), validates full auth
chain (OAuth + Cognito + AWS), discovers TS devices via DescribeThing,
stores device metadata in config entry. Supports reauth flow."
```

---

### Task 11: Translations and Manifest (`en.json`, `manifest.json`)

**Files:**
- Rewrite: `custom_components/maytag_laundry/translations/en.json`
- Modify: `custom_components/maytag_laundry/manifest.json`

- [ ] **Step 1: Update translations**

Rewrite `custom_components/maytag_laundry/translations/en.json`:
```json
{
  "title": "Maytag Laundry",
  "config": {
    "step": {
      "user": {
        "title": "Connect your Whirlpool account",
        "description": "Enter your Maytag, Whirlpool, or KitchenAid app credentials.",
        "data": {
          "email": "Email",
          "password": "Password",
          "brand": "Brand"
        }
      }
    },
    "error": {
      "auth_failed": "Authentication failed. Check your email, password, and brand selection.",
      "no_devices": "No supported appliances found on this account. This integration only supports newer (TS) appliances.",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This account is already configured."
    }
  }
}
```

- [ ] **Step 2: Update manifest.json**

Write `custom_components/maytag_laundry/manifest.json`:
```json
{
  "domain": "maytag_laundry",
  "name": "Maytag Laundry",
  "version": "1.0.0",
  "requirements": ["awsiotsdk>=1.0.0", "boto3>=1.20.0"],
  "documentation": "https://github.com/pickerin/maytag_laundry_homeassistant",
  "issue_tracker": "https://github.com/pickerin/maytag_laundry_homeassistant/issues",
  "codeowners": ["@pickerin"],
  "config_flow": true,
  "iot_class": "cloud_push"
}
```

Note: `iot_class` changed from `cloud_polling` to `cloud_push` since the primary data path is MQTT push with poll as fallback. `boto3` is added as a requirement since we use it for `describe_thing` during discovery.

- [ ] **Step 3: Also create `translations/strings.json`** (HA uses this as the canonical source)

Write `custom_components/maytag_laundry/translations/strings.json` with the same content as `en.json`.

- [ ] **Step 4: Commit**

```bash
git add custom_components/maytag_laundry/translations/ custom_components/maytag_laundry/manifest.json
git commit -m "feat: update translations and manifest for v1.0.0

Add brand selector strings, error messages for auth/discovery failures.
Update manifest to awsiotsdk + boto3, bump version to 1.0.0,
change iot_class to cloud_push."
```

---

### Task 12: End-to-End Smoke Test

**Files:**
- No new files — test on a real HA instance or with the tools scripts.

- [ ] **Step 1: Verify all modules import cleanly**

Run:
```bash
cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant"
.venv/bin/python -c "
from custom_components.maytag_laundry.const import DOMAIN, BRAND_CONFIG
from custom_components.maytag_laundry.api import WhirlpoolTSClient, AuthError, DeviceInfo
from custom_components.maytag_laundry.sensor import extract_appliance_type, extract_sensor_value
print('All imports OK')
print(f'Domain: {DOMAIN}')
print(f'Brands: {list(BRAND_CONFIG.keys())}')
"
```
Expected: "All imports OK" with domain and brands listed.

- [ ] **Step 2: Run the full unit test suite**

Run:
```bash
cd "/Users/pickerin/Documents/Development/Home Assistant/maytag_laundry_homeassistant"
.venv/bin/python -m pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 3: Run a live API test**

Run the existing `tools/ts_mqtt2.py` to confirm the auth chain still works end-to-end against the real Whirlpool API. If appliances are powered on, verify getState responses arrive.

- [ ] **Step 4: Final commit — update CLAUDE.md**

Update `CLAUDE.md` to reflect the new architecture, then commit:

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for v1.0.0 TS appliance architecture"
```

---

### Task 13: Cleanup

- [ ] **Step 1: Remove debug prints from patched library files**

Remove the debug `print()` statement from `.venv/lib/python3.10/site-packages/whirlpool/auth.py` (line with `AUTH response status=`). This was added during investigation and is no longer needed.

- [ ] **Step 2: Add .gitignore**

Create `.gitignore`:
```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
build/
tools/apk/
.pytest_cache/
```

- [ ] **Step 3: Add LICENSE**

Create `LICENSE` with MIT license text, copyright holder: Robert Pickering.

- [ ] **Step 4: Commit**

```bash
git add .gitignore LICENSE
git commit -m "chore: add .gitignore and MIT license"
```
