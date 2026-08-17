"""Tests for the PoolstationDataUpdateCoordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientResponseError, RequestInfo
from conftest import make_pool
from homeassistant.exceptions import ConfigEntryAuthFailed
from pypoolstation import AuthenticationException
from yarl import URL

from custom_components.poolstation import PoolstationDataUpdateCoordinator
from custom_components.poolstation.const import AUTH_RETRIES


async def test_update_data_success(hass):
    """A successful sync resets the auth retry counter."""
    pool = make_pool()
    pool.sync_info = AsyncMock()
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)

    await coordinator._async_update_data()

    pool.sync_info.assert_awaited_once()
    assert coordinator.auth_retries == AUTH_RETRIES


async def test_update_data_resets_after_errors(hass):
    """The auth retry counter is reset after a successful update."""
    pool = make_pool()
    pool.sync_info = AsyncMock(
        side_effect=[AuthenticationException("oops"), None]
    )
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    assert coordinator.auth_retries == AUTH_RETRIES


async def test_update_data_client_error_ignored(hass):
    """A client response error is ignored (server side timeout)."""
    pool = make_pool()
    request_info = RequestInfo(
        "GET", URL("https://poolstation.net/api/pool"), [], None
    )
    pool.sync_info = AsyncMock(
        side_effect=ClientResponseError(request_info, (), status=500)
    )
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)

    result = await coordinator._async_update_data()

    assert result is None
    assert coordinator.auth_retries == AUTH_RETRIES


async def test_update_data_auth_error_decrements(hass):
    """Auth errors decrement the retry counter until it is exhausted."""
    pool = make_pool()
    pool.sync_info = AsyncMock(side_effect=AuthenticationException("expired"))
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)

    await coordinator._async_update_data()
    assert coordinator.auth_retries == AUTH_RETRIES - 1

    with pytest.raises(ConfigEntryAuthFailed):
        for _ in range(AUTH_RETRIES):
            await coordinator._async_update_data()
