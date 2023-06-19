"""Support for Poolstation binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pypoolstation import Pool

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity


@dataclass
class PoolstationentityDescriptionMixin:
    """Mixin values for Poolstation entities."""

    is_on_fn: Callable[[Pool], bool]
    has_fn: Callable[[Pool], bool]

@dataclass
class PoolstationBinarySensorEntityDescription(
    BinarySensorEntityDescription, PoolstationentityDescriptionMixin
):
    """Class describing Poolstation binary sensor entities."""

ENTITY_DESCRIPTIONS = (
    PoolstationBinarySensorEntityDescription(
        key="water_flow",
        name="Water Flow",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda pool: pool.waterflow_problem,
        has_fn=lambda pool: pool.waterflow_problem is not None,
    ),
    PoolstationBinarySensorEntityDescription(
        key="binary_input_1",
        name="Digital input 1",
        is_on_fn=lambda pool: pool.binary_input_1,
        has_fn=lambda pool: pool.binary_input_1 is not None,
    ),
    PoolstationBinarySensorEntityDescription(
        key="binary_input_2",
        name="Digital input 2",
        is_on_fn=lambda pool: pool.binary_input_2,
        has_fn=lambda pool: pool.binary_input_2 is not None,
    ),
    PoolstationBinarySensorEntityDescription(
        key="binary_input_3",
        name="Digital input 3",
        is_on_fn=lambda pool: pool.binary_input_3,
        has_fn=lambda pool: pool.binary_input_3 is not None,
    ),
    PoolstationBinarySensorEntityDescription(
        key="binary_input_4",
        name="Digital input 4",
        is_on_fn=lambda pool: pool.binary_input_4,
        has_fn=lambda pool: pool.binary_input_4 is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool binary sensors."""
    pools = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[PoolEntity] = []
    for pool_id, pool in pools.items():
        coordinator = coordinators[pool_id]
        for description in ENTITY_DESCRIPTIONS:
            entities.append(PoolBinarySensorEntity(pool, coordinator, description))

    async_add_entities(entities)



class PoolBinarySensorEntity(PoolEntity, BinarySensorEntity):
    """Defines a Poolstation binary sensor entity."""

    entity_description: PoolstationBinarySensorEntityDescription

    def __init__(
        self,
        pool: Pool,
        coordinator: PoolstationDataUpdateCoordinator,
        description: PoolstationBinarySensorEntityDescription,
    ) -> None:
        """Initialize the pool binary sensor"""
        super().__init__(pool, coordinator, " " + description.name)
        self.entity_description = description


    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.pool)
