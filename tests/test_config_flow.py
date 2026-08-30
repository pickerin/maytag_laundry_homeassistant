"""Tests for the reauth config flow."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.maytag_laundry.api import AuthError
from custom_components.maytag_laundry.config_flow import MaytagLaundryConfigFlow
from custom_components.maytag_laundry.const import CONF_BRAND, CONF_EMAIL, CONF_PASSWORD


@pytest.fixture
def flow():
    f = MaytagLaundryConfigFlow()
    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "old",
        CONF_BRAND: "Maytag",
    }
    f._get_reauth_entry = MagicMock(return_value=entry)
    f.async_update_reload_and_abort = MagicMock(
        return_value={"type": "abort", "reason": "reauth_successful"}
    )
    f.async_show_form = MagicMock(return_value={"type": "form"})
    f.async_set_unique_id = AsyncMock()
    f._validate_and_discover = AsyncMock(return_value={"SAID1": MagicMock()})
    return f


class TestReauth:
    @pytest.mark.asyncio
    async def test_reauth_updates_entry(self, flow):
        """Valid new password updates the existing entry — no unique_id abort."""
        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "new"})

        assert result["reason"] == "reauth_successful"
        flow._validate_and_discover.assert_awaited_once_with(
            "test@example.com", "new", "Maytag"
        )
        flow.async_update_reload_and_abort.assert_called_once_with(
            flow._get_reauth_entry(), data_updates={CONF_PASSWORD: "new"}
        )
        flow.async_set_unique_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_reauth_bad_password_shows_form(self, flow):
        """AuthError re-shows the form with an error instead of aborting."""
        flow._validate_and_discover.side_effect = AuthError("bad password")

        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "wrong"})

        assert result["type"] == "form"
        assert flow.async_show_form.call_args.kwargs["errors"] == {"base": "auth_failed"}
        flow.async_update_reload_and_abort.assert_not_called()

    @pytest.mark.asyncio
    async def test_reauth_entry_starts_with_form(self, flow):
        """async_step_reauth shows the confirm form, not the user step."""
        result = await flow.async_step_reauth(flow._get_reauth_entry().data)
        assert result["type"] == "form"
        assert flow.async_show_form.call_args.kwargs["step_id"] == "reauth_confirm"
