"""Tests for WhirlpoolTSClient."""
import base64
import json
import time
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
        import time
        client.access_token = "fake-token"
        client._oauth_expires_at = time.time() + 3600  # token is valid

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

        mock_iot = MagicMock()
        mock_iot.describe_thing.return_value = {
            "thingName": "SAID1",
            "thingTypeName": "MTW7205RR0",
            "attributes": {
                "Brand": "MAYTAG",
                "Category": "LAUNDRY",
                "Serial": "CE3600456",
                "Name": "4d617974616720576173686572",
                "WifiMacAddress": "3C:8A:1F:0C:7D:50",
            },
        }

        with patch("custom_components.maytag_laundry.api.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_iot
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

        mock_iot = MagicMock()
        mock_iot.describe_thing.return_value = {
            "thingName": "SAID1",
            "thingTypeName": "MTW7205RR0",
            "attributes": {
                "Brand": "MAYTAG",
                "Category": "LAUNDRY",
                "Serial": "SER1",
                "Name": "4d617974616720576173686572",
            },
        }

        with patch("custom_components.maytag_laundry.api.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_iot
            await client.discover_devices()

        assert "SAID1" in client.devices
        assert client.devices["SAID1"].model == "MTW7205RR0"
