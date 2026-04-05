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
import boto3

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

    @staticmethod
    def _decode_hex_name(hex_name: str) -> str:
        """Decode hex-encoded device name to UTF-8 string."""
        try:
            return bytes.fromhex(hex_name).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return hex_name

    async def _describe_thing(self, said: str) -> DeviceInfo:
        """Call AWS IoT DescribeThing API using boto3 (SigV4-signed).

        boto3 is called in a thread executor to avoid blocking the event loop.
        Only runs during device discovery — not in the polling loop.
        """
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
                _LOGGER.info(
                    "Discovered device: %s (%s, %s)", device.name, device.model, device.said
                )
            except Exception:
                _LOGGER.exception("Failed to describe thing %s", said)

        return self.devices
