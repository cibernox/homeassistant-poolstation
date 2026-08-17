"""Tests for the Poolstation config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType
from pypoolstation import AuthenticationException, TwoFactorAuthRequiredException

from custom_components.poolstation.const import CONF_AUTH_CODE, DOMAIN, TOKEN

EMAIL = "user@example.com"
PASSWORD = "secret"


async def _start_user_flow(hass) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )


async def test_user_step_shows_form(hass, mock_account):
    """The first user step shows the login form."""
    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_login_creates_entry(hass, mock_account):
    """A successful login creates a config entry with the token."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[TOKEN] == "test-token"
    assert entry.data[CONF_EMAIL] == EMAIL
    assert entry.data[CONF_PASSWORD] == PASSWORD


async def test_user_login_duplicate_unique_id_aborts(hass, mock_account):
    """Setting up the same account twice aborts with already_configured."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL.upper(), CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_login_invalid_auth(hass, mock_account):
    """Invalid credentials show the form with an error."""
    mock_account.login.side_effect = AuthenticationException("bad credentials")
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_login_connection_error(hass, mock_account):
    """Connection problems show the form with a cannot_connect error."""
    mock_account.login.side_effect = TimeoutError()
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_login_two_factor(hass, mock_account):
    """A 2FA challenge is followed by the code step, then a created entry."""
    async def login_with_mfa(login_code: str = "") -> str:
        nonlocal mfa_calls
        mfa_calls += 1
        if mfa_calls == 1:
            raise TwoFactorAuthRequiredException()
        return "mfa-token"

    mfa_calls = 0
    mock_account.login.side_effect = login_with_mfa
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(DOMAIN)[0].data[TOKEN] == "mfa-token"
    mock_account.login.assert_awaited_with(login_code="123456")


async def test_user_login_two_factor_bad_code_retries(hass, mock_account):
    """A rejected 2FA code re-shows the code step instead of the credentials."""
    async def login_with_mfa(login_code: str = "") -> str:
        nonlocal mfa_calls
        mfa_calls += 1
        if mfa_calls == 1:
            raise TwoFactorAuthRequiredException()
        if login_code == "wrong":
            raise AuthenticationException("bad code")
        return "mfa-token"

    mfa_calls = 0
    mock_account.login.side_effect = login_with_mfa
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    assert result["step_id"] == "two_factor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_CODE: "wrong"}
    )

    # The 2FA step is re-shown with the error, not the credentials form.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor"
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(DOMAIN)[0].data[TOKEN] == "mfa-token"


async def test_reauth_updates_entry(hass, mock_account):
    """A reauth flow with valid credentials updates the entry and reloads it."""
    # Create the entry first through the normal user flow
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    mock_account.login.return_value = "reauth-token"
    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[TOKEN] == "reauth-token"
    assert entry.data[CONF_PASSWORD] == "new-password"
    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_reauth_two_factor_bad_code_retries(hass, mock_account):
    """A rejected 2FA code during reauth re-shows the code step."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    async def login_with_mfa(login_code: str = "") -> str:
        nonlocal mfa_calls
        mfa_calls += 1
        if mfa_calls == 1:
            raise TwoFactorAuthRequiredException()
        if login_code == "wrong":
            raise AuthenticationException("bad code")
        return "mfa-token"

    mfa_calls = 0
    mock_account.login.side_effect = login_with_mfa
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    assert result["step_id"] == "reauth_two_factor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_CODE: "wrong"}
    )

    # The 2FA step is re-shown with the error, not the credentials form.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_two_factor"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AUTH_CODE: "123456"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[TOKEN] == "mfa-token"


async def test_reauth_two_factor(hass, mock_account):
    """Reauth supports the 2FA step and updates the entry on success."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    async def login_with_mfa(login_code: str = "") -> str:
        nonlocal mfa_calls
        mfa_calls += 1
        if mfa_calls == 1:
            raise TwoFactorAuthRequiredException()
        return "mfa-token"

    mfa_calls = 0
    mock_account.login.side_effect = login_with_mfa
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_two_factor"

    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AUTH_CODE: "123456"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[TOKEN] == "mfa-token"


async def test_reauth_invalid_auth_shows_error_and_retries(hass, mock_account):
    """Reauth with bad credentials re-shows the form so the user can retry."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    mock_account.login.side_effect = AuthenticationException()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "bad-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    # The user corrects the password and retries; the flow succeeds.
    mock_account.login.side_effect = None
    mock_account.login.return_value = "reauth-token"
    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "good-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[TOKEN] == "reauth-token"
    mock_reload.assert_awaited_once_with(entry.entry_id)
