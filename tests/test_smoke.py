"""Smoke tests: the integration imports and entities can be instantiated."""
from __future__ import annotations

from unittest.mock import MagicMock

from conftest import make_pool, make_relay
from homeassistant.core import CoreState

from custom_components.poolstation import PoolstationDataUpdateCoordinator
from custom_components.poolstation.const import DOMAIN
from custom_components.poolstation.sensor import (
    ENTITY_DESCRIPTIONS as SENSOR_DESCRIPTIONS,
)
from custom_components.poolstation.sensor import (
    PoolSensorEntity,
)


async def test_hass_fixture(hass):
    """The hass fixture provides a running HomeAssistant instance."""
    assert hass.state is CoreState.running


def test_integration_imports():
    """All integration modules import cleanly."""
    import custom_components.poolstation
    import custom_components.poolstation.binary_sensor
    import custom_components.poolstation.config_flow
    import custom_components.poolstation.const
    import custom_components.poolstation.entity
    import custom_components.poolstation.number
    import custom_components.poolstation.sensor
    import custom_components.poolstation.switch
    import custom_components.poolstation.util

    assert custom_components.poolstation.DOMAIN == DOMAIN


async def test_sensor_entity(hass):
    """A sensor entity can be created and reports a mocked value."""
    pool = make_pool(current_ph=7.2)
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)
    description = SENSOR_DESCRIPTIONS[0]
    entity = PoolSensorEntity(pool, coordinator, description)

    assert entity.entity_description is description
    assert entity.unique_id == "pool-1 pH"
    assert entity.native_value == 7.2
    assert "Test Pool" in entity.name


async def test_switch_entity(hass):
    """A relay switch entity can be created and reflects the relay state."""
    from custom_components.poolstation.switch import PoolRelaySwitch

    relay = make_relay(name="Pump", active=True)
    pool = make_pool(relays=[relay])
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)
    entity = PoolRelaySwitch(pool, coordinator, relay)

    assert entity.is_on is True
    assert "Relay Pump" in entity.name


def test_create_account():
    """create_account wraps the given credentials in a pypoolstation Account."""
    from pypoolstation import Account

    from custom_components.poolstation.util import create_account

    account = create_account(MagicMock(), "user@example.com", "secret")
    assert isinstance(account, Account)


async def test_coordinator_defaults(hass):
    """The coordinator tracks the pool and resets the auth retry counter."""
    from custom_components.poolstation.const import AUTH_RETRIES

    pool = make_pool()
    coordinator = PoolstationDataUpdateCoordinator(hass, pool)

    assert coordinator.pool is pool
    assert coordinator.auth_retries == AUTH_RETRIES
