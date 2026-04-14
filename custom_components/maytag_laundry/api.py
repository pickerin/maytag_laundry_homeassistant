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
from .profiles import ApplianceProfile, load_profile

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
    capability_part_number: str = ""
    profile: Optional[ApplianceProfile] = None


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
        self._client_credentials = brand_cfg["client_credentials"]
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribed_topics: List[str] = []
        self._refresh_task: Optional[asyncio.Task] = None

    def _decode_jwt(self, token: str) -> dict:
        """Decode JWT payload without signature verification."""
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.b64decode(payload_b64))

    async def authenticate(self) -> None:
        """Step 1: OAuth password grant. Populates access_token, ts_saids, account_id.

        Tries each client credential set in order until one succeeds.
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/3.12.0",
        }

        last_error = None
        for creds in self._client_credentials:
            auth_data = {
                "grant_type": "password",
                "username": self._email,
                "password": self._password,
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            }

            async with self._session.post(
                self._oauth_url, data=auth_data, headers=headers
            ) as resp:
                if resp.status == 423:
                    raise AuthError("Account is locked — reset password at brand website")
                if resp.status == 200:
                    data = await resp.json()
                    break
                last_error = await resp.text()
                _LOGGER.debug(
                    "OAuth attempt with %s failed (HTTP %s): %s",
                    creds["client_id"], resp.status, last_error,
                )
        else:
            raise AuthError(f"OAuth failed with all credential sets: {last_error}")

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

        Both client creation and the API call run in an executor
        to avoid blocking the event loop.
        """
        loop = asyncio.get_running_loop()

        def _boto3_describe():
            iot = boto3.client(
                "iot",
                region_name=self._aws_region,
                aws_access_key_id=self._aws_access_key,
                aws_secret_access_key=self._aws_secret_key,
                aws_session_token=self._aws_session_token,
            )
            return iot.describe_thing(thingName=said)

        result = await loop.run_in_executor(None, _boto3_describe)

        attrs = result.get("attributes", {})
        return DeviceInfo(
            said=said,
            model=result.get("thingTypeName", ""),
            brand=attrs.get("Brand", ""),
            category=attrs.get("Category", ""),
            serial=attrs.get("Serial", ""),
            name=self._decode_hex_name(attrs.get("Name", said)),
            wifi_mac=attrs.get("WifiMacAddress", ""),
            capability_part_number=attrs.get("CapabilityPartNumber", ""),
        )

    async def discover_devices(self) -> Dict[str, DeviceInfo]:
        """Discover all TS devices by calling DescribeThing for each TS_SAID."""
        await self.ensure_aws_credentials()

        for said in self.ts_saids:
            try:
                device = await self._describe_thing(said)
                device.profile = load_profile(device.capability_part_number)
                self.devices[said] = device
                _LOGGER.info(
                    "Discovered device: %s (%s, %s, profile=%s)",
                    device.name, device.model, device.said,
                    device.profile.appliance_type if device.profile else "none",
                )
            except Exception:
                _LOGGER.exception("Failed to describe thing %s", said)

        return self.devices

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

    # --- MQTT helpers to avoid blocking the event loop ---

    async def _await_future(self, future, timeout: float = 15) -> Any:
        """Await an awscrt Future without blocking the asyncio event loop.

        awscrt futures are threading futures, not asyncio futures.
        We must run .result() in an executor to avoid blocking HA.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: future.result(timeout=timeout))

    # --- MQTT connection ---

    async def connect(self) -> None:
        """Establish MQTT WebSocket connection and subscribe to all device topics."""
        await self.ensure_aws_credentials()

        # Capture the event loop for use in MQTT callbacks (which run on awscrt threads)
        self._loop = asyncio.get_running_loop()

        await self._do_mqtt_connect()

        # Start proactive credential refresh — AWS creds expire in ~1 hour
        if self._refresh_task:
            self._refresh_task.cancel()
        self._refresh_task = self._loop.create_task(self._credential_refresh_loop())

    async def _do_mqtt_connect(self) -> None:
        """Build MQTT connection, connect, and subscribe to all device topics.

        Uses current AWS credentials. Called by connect() and _rebuild_mqtt_connection().
        """
        from awscrt import mqtt, auth as awsauth
        from awsiot import mqtt_connection_builder

        client_id = f"maytag-laundry-{uuid.uuid4().hex[:8]}"

        # Build the connection object in an executor — the builder does
        # blocking TLS/socket setup internally.
        def _build_connection():
            credentials_provider = awsauth.AwsCredentialsProvider.new_static(
                access_key_id=self._aws_access_key,
                secret_access_key=self._aws_secret_key,
                session_token=self._aws_session_token,
            )
            return mqtt_connection_builder.websockets_with_default_aws_signing(
                endpoint=self._iot_endpoint,
                region=self._aws_region,
                credentials_provider=credentials_provider,
                client_id=client_id,
                on_connection_interrupted=self._on_connection_interrupted,
                on_connection_resumed=self._on_connection_resumed,
            )

        self._mqtt_connection = await self._loop.run_in_executor(None, _build_connection)

        connect_future = self._mqtt_connection.connect()
        await self._await_future(connect_future, timeout=15)
        _LOGGER.info("MQTT connected to %s as %s", self._iot_endpoint, client_id)

        # Subscribe to topics for each discovered device
        self._subscribed_topics = []
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
                await self._await_future(sub_future, timeout=10)
                self._subscribed_topics.append(topic)
                _LOGGER.debug("Subscribed: %s", topic)
                await asyncio.sleep(0.5)  # pace subscriptions per IoT policy

    async def _credential_refresh_loop(self) -> None:
        """Background task: refresh AWS credentials and rebuild MQTT before they expire.

        AWS temporary credentials last ~1 hour. We rebuild the connection 10 minutes
        before expiry so the static credentials provider never sees expired creds.
        """
        try:
            while True:
                # Sleep until 10 minutes before credential expiry
                refresh_in = max(60.0, self._aws_creds_expire_at - time.time() - 600)
                _LOGGER.debug("AWS credential refresh scheduled in %.0f seconds", refresh_in)
                await asyncio.sleep(refresh_in)
                _LOGGER.info("Proactively refreshing AWS credentials before expiry")
                await self._rebuild_mqtt_connection()
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("Credential refresh loop failed")

    async def _rebuild_mqtt_connection(self) -> None:
        """Force credential refresh and rebuild the MQTT connection.

        Disconnects the existing connection (with its baked-in stale credentials),
        obtains fresh AWS credentials, then reconnects and re-subscribes.
        """
        # Force credential refresh by invalidating the cache
        self._aws_creds_expire_at = 0
        await self.ensure_aws_credentials()

        # Disconnect old connection
        if self._mqtt_connection:
            try:
                disconnect_future = self._mqtt_connection.disconnect()
                await self._await_future(disconnect_future, timeout=10)
            except Exception:
                _LOGGER.warning("Error disconnecting before MQTT rebuild (continuing)")
            self._mqtt_connection = None

        # Reconnect with fresh credentials
        await self._do_mqtt_connect()
        _LOGGER.info("MQTT connection rebuilt with fresh credentials")

    async def _resubscribe(self) -> None:
        """Re-subscribe to all tracked topics after awscrt auto-reconnect without session."""
        if not self._mqtt_connection or not self._subscribed_topics:
            return
        from awscrt import mqtt
        for topic in list(self._subscribed_topics):
            try:
                sub_future, _ = self._mqtt_connection.subscribe(
                    topic=topic,
                    qos=mqtt.QoS.AT_LEAST_ONCE,
                    callback=self._on_mqtt_message,
                )
                await self._await_future(sub_future, timeout=10)
                _LOGGER.debug("Re-subscribed: %s", topic)
                await asyncio.sleep(0.5)
            except Exception:
                _LOGGER.exception("Failed to re-subscribe to %s", topic)

    def _on_connection_interrupted(self, connection, error, **kwargs):
        _LOGGER.warning("MQTT connection interrupted: %s", error)

    def _on_connection_resumed(self, connection, return_code, session_present, **kwargs):
        _LOGGER.info("MQTT connection resumed (rc=%s, session_present=%s)", return_code, session_present)
        if self._loop is None:
            return
        # Re-subscribe if the broker did not restore the session (subscriptions are lost)
        if not session_present:
            asyncio.run_coroutine_threadsafe(self._resubscribe(), self._loop)
        # Notify coordinator callbacks so entities refresh
        for said, callbacks in self._callbacks.items():
            for cb in callbacks:
                self._loop.call_soon_threadsafe(cb, said, None)

    def _on_mqtt_message(self, topic: str, payload: bytes, dup, qos, retain, **kwargs):
        """Handle incoming MQTT messages — state updates and command responses.

        IMPORTANT: This callback runs on an awscrt thread, NOT the asyncio event loop.
        We store state directly (dict assignment is thread-safe in CPython) and then
        schedule callbacks on the event loop via call_soon_threadsafe.
        """
        try:
            msg = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.error("Failed to decode MQTT message on %s", topic)
            return

        _LOGGER.debug("MQTT message on %s: %s", topic, str(msg)[:200])

        parts = topic.split("/")
        if len(parts) < 3:
            return
        said = parts[2]

        if topic.startswith("cmd/") and "response" in topic:
            state = msg.get("payload", {})
        elif topic.startswith("dt/") and "state/update" in topic:
            state = msg
        else:
            return

        # Store state (dict assignment is atomic in CPython)
        self._device_state[said] = state

        # Schedule callbacks on the event loop thread
        if self._loop is not None:
            for cb in self._callbacks.get(said, []):
                self._loop.call_soon_threadsafe(cb, said, state)

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
        await self._await_future(publish_future, timeout=10)
        _LOGGER.debug("Published getState for %s", said)

        # Wait for response to arrive via _on_mqtt_message
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
        """Disconnect MQTT and cancel background credential refresh task."""
        # Cancel the credential refresh background task
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None

        if self._mqtt_connection:
            try:
                disconnect_future = self._mqtt_connection.disconnect()
                await self._await_future(disconnect_future, timeout=10)
            except Exception:
                _LOGGER.exception("Error disconnecting MQTT")
            self._mqtt_connection = None
            self._loop = None
            _LOGGER.info("MQTT disconnected")
