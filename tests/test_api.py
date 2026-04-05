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
