"""Tests for async_setup_entry / async_unload_entry.

Note: in current Home Assistant versions, ``ConfigEntries.async_add`` adds
*and* sets up the entry, so setup is triggered by creating the entry inside
the relevant patch blocks.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
from conftest import make_pool, make_relay
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from pypoolstation import AuthenticationException, Pool, TwoFactorAuthRequiredException

from custom_components.poolstation import PLATFORMS
from custom_components.poolstation.const import COORDINATORS, DEVICES, DOMAIN


async def make_entry(hass, data=None) -> ConfigEntry:
    """Add a config entry (which also starts its setup)."""
    entry = ConfigEntry(
        domain=DOMAIN,
        data=data or {
            CONF_TOKEN: "token",
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
        },
        version=1,
        title="user@example.com",
        source="user",
        unique_id="user@example.com",
        minor_version=1,
        options={},
        discovery_keys={},
        subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    return entry


async def test_setup_entry(hass, mock_account):
    """Setup creates one coordinator and device entry per pool."""
    pool = make_pool(pool_id="pool-1", relays=[make_relay()])
    with (
        patch.object(Pool, "get_all_pools", AsyncMock(return_value=[pool])) as mock_pools,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        ) as mock_forward,
    ):
        entry = await make_entry(hass)

    assert entry.state is ConfigEntryState.LOADED
    data = hass.data[DOMAIN][entry.entry_id]
    assert data[DEVICES]["pool-1"] is pool
    assert data[COORDINATORS]["pool-1"].pool is pool
    mock_pools.assert_awaited_once()
    mock_forward.assert_awaited_once_with(entry, PLATFORMS)


async def test_setup_entry_client_error(hass, mock_account):
    """A client error during setup makes the entry not ready."""
    with patch.object(
        Pool, "get_all_pools", AsyncMock(side_effect=aiohttp.ClientError("nope"))
    ):
        entry = await make_entry(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_entry_auth_error_relogin(hass, mock_account):
    """An auth error triggers a re-login and stores the new token."""
    pool = make_pool(pool_id="pool-1")
    mock_account.login.return_value = "fresh-token"
    with (
        patch.object(
            Pool,
            "get_all_pools",
            AsyncMock(side_effect=[AuthenticationException("expired"), [pool]]),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        entry = await make_entry(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_TOKEN] == "fresh-token"
    mock_account.login.assert_awaited_once()


async def test_setup_entry_auth_error_two_factor(hass, mock_account):
    """An auth error requiring 2FA fails the setup (reauth flow handles it)."""
    mock_account.login.side_effect = TwoFactorAuthRequiredException()
    with (
        patch.object(
            Pool, "get_all_pools", AsyncMock(side_effect=AuthenticationException())
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        entry = await make_entry(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_auth_error_invalid_credentials(hass, mock_account):
    """A re-login failure fails the setup."""
    mock_account.login.side_effect = AuthenticationException("wrong")
    with (
        patch.object(
            Pool, "get_all_pools", AsyncMock(side_effect=AuthenticationException())
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        entry = await make_entry(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass, mock_account):
    """Unloading the entry removes its data."""
    pool = make_pool(pool_id="pool-1")
    with (
        patch.object(Pool, "get_all_pools", AsyncMock(return_value=[pool])),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        entry = await make_entry(hass)

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    assert entry.entry_id not in hass.data[DOMAIN]
