"""Tests for the sensor, number, switch and binary_sensor platforms."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_pool, make_relay

from custom_components.poolstation import PoolstationDataUpdateCoordinator
from custom_components.poolstation.binary_sensor import (
    ENTITY_DESCRIPTIONS as BINARY_SENSOR_DESCRIPTIONS,
)
from custom_components.poolstation.binary_sensor import (
    PoolBinarySensorEntity,
)
from custom_components.poolstation.binary_sensor import (
    async_setup_entry as binary_sensor_setup,
)
from custom_components.poolstation.const import COORDINATORS, DEVICES, DOMAIN
from custom_components.poolstation.number import (
    ENTITY_DESCRIPTIONS as NUMBER_DESCRIPTIONS,
)
from custom_components.poolstation.number import (
    PoolNumberEntity,
)
from custom_components.poolstation.number import (
    async_setup_entry as number_setup,
)
from custom_components.poolstation.sensor import (
    ENTITY_DESCRIPTIONS as SENSOR_DESCRIPTIONS,
)
from custom_components.poolstation.sensor import (
    PoolSensorEntity,
)
from custom_components.poolstation.sensor import (
    async_setup_entry as sensor_setup,
)
from custom_components.poolstation.switch import (
    PoolRelaySwitch,
)
from custom_components.poolstation.switch import (
    async_setup_entry as switch_setup,
)

ENTRY_ID = "entry-1"


def install_pools(hass, pools):
    """Register pools and coordinators in hass.data the way setup_entry does."""
    hass.data[DOMAIN] = {
        ENTRY_ID: {
            COORDINATORS: {
                pool.id: PoolstationDataUpdateCoordinator(hass, pool) for pool in pools
            },
            DEVICES: {pool.id: pool for pool in pools},
        }
    }


def make_config_entry() -> MagicMock:
    entry = MagicMock()
    entry.entry_id = ENTRY_ID
    return entry


async def test_sensor_setup(hass):
    """Sensors are created for every pool and description."""
    pool = make_pool()
    install_pools(hass, [pool])
    async_add_entities = MagicMock()

    await sensor_setup(hass, make_config_entry(), async_add_entities)

    assert async_add_entities.call_count == 1
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == len(SENSOR_DESCRIPTIONS)
    assert all(isinstance(entity, PoolSensorEntity) for entity in entities)


async def test_sensor_values(hass):
    """Sensors report the pool attribute they were described with."""
    pool = make_pool(
        current_ph=7.1,
        temperature=22.5,
        salt_concentration=3.4,
        percentage_electrolysis=64,
        current_orp=780,
        current_clppm=1.2,
        current_uv_timer=3.5,
        total_uv_timer=102.0,
    )
    install_pools(hass, [pool])
    coordinator = hass.data[DOMAIN][ENTRY_ID][COORDINATORS][pool.id]

    values = [
        PoolSensorEntity(pool, coordinator, description).native_value
        for description in SENSOR_DESCRIPTIONS
    ]
    assert values == [7.1, 22.5, 3.4, 64, 780, 1.2, 3.5, 102.0]


async def test_sensor_setup_skips_absent_attributes(hass):
    """Only sensors for attributes the pool actually has are created."""
    pool = make_pool(
        current_uv_timer=None,
        total_uv_timer=None,
        current_clppm=None,
        temperature=None,
    )
    install_pools(hass, [pool])
    async_add_entities = MagicMock()

    await sensor_setup(hass, make_config_entry(), async_add_entities)

    entities = async_add_entities.call_args[0][0]
    created_keys = {entity.entity_description.key for entity in entities}
    assert "uv_current_timer" not in created_keys
    assert "uv_total_timer" not in created_keys
    assert "free_chlorine" not in created_keys
    assert "temperature" not in created_keys
    assert "pH" in created_keys


async def test_sensor_multiple_pools(hass):
    """Entities are created per pool."""
    pool_a = make_pool(pool_id="a")
    pool_b = make_pool(pool_id="b")
    install_pools(hass, [pool_a, pool_b])
    async_add_entities = MagicMock()

    await sensor_setup(hass, make_config_entry(), async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2 * len(SENSOR_DESCRIPTIONS)
    unique_ids = {entity.unique_id for entity in entities}
    assert len(unique_ids) == 2 * len(SENSOR_DESCRIPTIONS)


async def test_number_setup(hass):
    """Numbers are created for every pool and description."""
    pool = make_pool()
    install_pools(hass, [pool])
    async_add_entities = MagicMock()

    await number_setup(hass, make_config_entry(), async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == len(NUMBER_DESCRIPTIONS)
    assert all(isinstance(entity, PoolNumberEntity) for entity in entities)


async def test_number_set_value(hass):
    """Setting a number calls the matching pool method with the value."""
    pool = make_pool(target_ph=7.0, target_orp=700, target_clppm=1.0)
    pool.set_target_ph = AsyncMock()
    pool.set_target_orp = AsyncMock()
    pool.set_target_clppm = AsyncMock()
    pool.set_target_percentage_electrolysis = AsyncMock()
    install_pools(hass, [pool])
    coordinator = hass.data[DOMAIN][ENTRY_ID][COORDINATORS][pool.id]

    by_key = {description.key: description for description in NUMBER_DESCRIPTIONS}
    cases = [
        ("target_ph", 7.2, pool.set_target_ph, 7.2),
        ("target_orp", 750, pool.set_target_orp, 750),
        ("target_chlorine", 1.5, pool.set_target_clppm, 1.5),
        ("target_production", 80, pool.set_target_percentage_electrolysis, 80),
    ]
    for key, value, mock_set, expected in cases:
        entity = PoolNumberEntity(pool, coordinator, by_key[key])
        with patch.object(entity, "async_write_ha_state"):
            await entity.async_set_native_value(value)
        mock_set.assert_awaited_once_with(expected)


async def test_device_info(hass):
    """Entities share device info with manufacturer and model."""
    pool = make_pool()
    install_pools(hass, [pool])
    coordinator = hass.data[DOMAIN][ENTRY_ID][COORDINATORS][pool.id]
    entity = PoolSensorEntity(
        pool, coordinator, SENSOR_DESCRIPTIONS[0]
    )

    assert entity.device_info == {
        "identifiers": {(DOMAIN, pool.id)},
        "manufacturer": "Fluidra",
        "model": "Poolstation",
        "name": pool.alias,
    }


async def test_switch_setup(hass):
    """One switch is created per relay."""
    relays = [make_relay(name="Pump"), make_relay(name="Light", active=True)]
    pool = make_pool(relays=relays)
    install_pools(hass, [pool])
    async_add_entities = MagicMock()

    await switch_setup(hass, make_config_entry(), async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert all(isinstance(entity, PoolRelaySwitch) for entity in entities)
    assert [entity.is_on for entity in entities] == [False, True]


async def test_switch_toggle(hass):
    """Turning a relay on/off calls set_active and updates the state."""
    relay = make_relay()
    pool = make_pool(relays=[relay])
    install_pools(hass, [pool])
    coordinator = hass.data[DOMAIN][ENTRY_ID][COORDINATORS][pool.id]
    entity = PoolRelaySwitch(pool, coordinator, relay)

    with patch.object(entity, "async_write_ha_state"):
        await entity.async_turn_on()
        assert entity.is_on is True
        await entity.async_turn_off()
        assert entity.is_on is False

    relay.set_active.assert_any_await(True)
    relay.set_active.assert_any_await(False)


async def test_switch_coordinator_update(hass):
    """A coordinator update refreshes the switch state from the relay."""
    relay = make_relay(active=True)
    pool = make_pool(relays=[relay])
    install_pools(hass, [pool])
    coordinator = hass.data[DOMAIN][ENTRY_ID][COORDINATORS][pool.id]
    entity = PoolRelaySwitch(pool, coordinator, relay)

    relay.active = False
    with patch.object(entity, "async_write_ha_state") as mock_write:
        entity._handle_coordinator_update()

    assert entity.is_on is False
    mock_write.assert_called_once()


async def test_binary_sensor_setup(hass):
    """Binary sensors are created for every pool and description."""
    pool = make_pool()
    install_pools(hass, [pool])
    async_add_entities = MagicMock()

    await binary_sensor_setup(hass, make_config_entry(), async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == len(BINARY_SENSOR_DESCRIPTIONS)
    assert all(isinstance(entity, PoolBinarySensorEntity) for entity in entities)


async def test_binary_sensor_setup_skips_absent_attributes(hass):
    """Only binary sensors for attributes the pool actually has are made."""
    pool = make_pool(
        uv_available=None,
        uv_enabled=None,
        uv_on=None,
        uv_ballast_problem=None,
        uv_fuse_problem=None,
    )
    install_pools(hass, [pool])
    async_add_entities = MagicMock()

    await binary_sensor_setup(hass, make_config_entry(), async_add_entities)

    entities = async_add_entities.call_args[0][0]
    created_keys = {entity.entity_description.key for entity in entities}
    assert "uv_available" not in created_keys
    assert "uv_enabled" not in created_keys
    assert "uv_light" not in created_keys
    assert "water_flow" in created_keys


async def test_binary_sensor_values(hass):
    """Binary sensors report the pool attribute they were described with."""
    pool = make_pool(
        waterflow_problem=True,
        binary_input_1=True,
        binary_input_2=False,
        binary_input_3=None,
        binary_input_4=None,
        uv_available=True,
        uv_enabled=False,
        uv_on=True,
        uv_ballast_problem=False,
        uv_fuse_problem=True,
    )
    install_pools(hass, [pool])
    coordinator = hass.data[DOMAIN][ENTRY_ID][COORDINATORS][pool.id]

    values = [
        PoolBinarySensorEntity(pool, coordinator, description).is_on
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    assert values == [True, True, False, None, None, True, False, True, False, True]
