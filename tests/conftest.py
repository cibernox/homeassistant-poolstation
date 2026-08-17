"""Shared fixtures and helpers for the poolstation integration tests."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries as config_entries_module
from homeassistant import loader as loader_module
from homeassistant.components.network.network import async_get_network
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame
from pypoolstation import Pool


def _pool_spec() -> Pool:
    """A real (empty) Pool instance used only as the spec for pool mocks."""
    return Pool(session=None, token=None, id="spec", logger=logging.getLogger("test"))


_POOL_SPEC = _pool_spec()


@pytest.fixture
async def hass(tmp_path):
    """Provide a running HomeAssistant instance with config entries initialized."""
    hass = HomeAssistant(str(tmp_path / "config"))
    await hass.async_start()
    store = config_entries_module.ConfigEntries(hass, {})
    hass.config_entries = store
    await store.async_initialize()
    frame.async_setup(hass)
    loader_module.async_setup(hass)
    await async_get_network(hass)
    try:
        yield hass
    finally:
        await hass.async_stop()


def make_pool(
    pool_id: str = "pool-1",
    alias: str = "Test Pool",
    relays: list | None = None,
    **attrs,
) -> MagicMock:
    """Create a mock pypoolstation.Pool with the given attribute values."""
    pool = MagicMock(spec=_POOL_SPEC)
    pool.id = pool_id
    pool.alias = alias
    pool.relays = relays or []
    for key, value in attrs.items():
        setattr(pool, key, value)
    return pool


def make_relay(name: str = "Pump", active: bool = False) -> MagicMock:
    """Create a mock pypoolstation.Relay."""
    relay = MagicMock()
    relay.name = name
    relay.active = active
    relay.set_active = AsyncMock(side_effect=lambda value: value)
    return relay


@pytest.fixture
def mock_account():
    """Provide a mocked pypoolstation.Account for config flow and setup."""
    from pypoolstation import Pool

    with (
        patch("custom_components.poolstation.config_flow.create_account") as flow_create,
        patch("custom_components.poolstation.config_flow.async_create_clientsession"),
        patch("custom_components.poolstation.create_account") as setup_create,
        # Creating an entry triggers an automatic setup; keep it hermetic.
        patch.object(Pool, "get_all_pools", AsyncMock(return_value=[])),
    ):
        account = make_account()
        flow_create.return_value = account
        setup_create.return_value = account
        yield account


def make_account(login_return_value: str = "test-token") -> MagicMock:
    """Create a mock pypoolstation.Account."""
    account = MagicMock()
    account.login = AsyncMock(return_value=login_return_value)
    return account
