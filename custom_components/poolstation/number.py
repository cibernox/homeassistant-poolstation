"""Support for Poolstation numbers."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pypoolstation import Pool

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity


@dataclass
class PoolstationNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Pool], int | float]
    set_value_fn: Callable[[Pool, int | float], Awaitable[Any]]


@dataclass
class PoolstationNumberEntityDescription(
    NumberEntityDescription, PoolstationNumberEntityDescriptionMixin
):
    """Class describing Poolstation number entities."""


MIN_PH = 6.0
MAX_PH = 8.0

MIN_ORP = 600
MAX_ORP = 850

MIN_CHLORINE = 0.30
MAX_CHLORINE = 3.50

ENTITY_DESCRIPTIONS = (
    PoolstationNumberEntityDescription(
        key="target_ph",
        name="Target PH",
        native_max_value=MAX_PH,
        native_min_value=MIN_PH,
        device_class=NumberDeviceClass.PH,
        native_step=0.01,
        value_fn=lambda pool: pool.target_ph,
        set_value_fn=lambda pool, value: pool.set_target_ph(value),
    ),
    PoolstationNumberEntityDescription(
        key="target_orp",
        name="Target ORP",
        icon="mdi:gauge",
        native_max_value=MAX_ORP,
        native_min_value=MIN_ORP,
        device_class=NumberDeviceClass.VOLTAGE,
        native_step=1,
        value_fn=lambda pool: pool.target_orp,
        set_value_fn=lambda pool, value: pool.set_target_orp(int(value)),
    ),
    PoolstationNumberEntityDescription(
        key="target_chlorine",
        name="Target Chlorine",
        icon="mdi:gauge",
        native_max_value=MAX_CHLORINE,
        native_min_value=MIN_CHLORINE,
        device_class=NumberDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_step=0.01,
        value_fn=lambda pool: pool.target_clppm,
        set_value_fn=lambda pool, value: pool.set_target_clppm(value),
    ),
    PoolstationNumberEntityDescription(
        key="target_production",
        name="Target Production",
        icon="mdi:gauge",
        native_max_value=100,
        native_min_value=0,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda pool: pool.target_percentage_electrolysis,
        set_value_fn=lambda pool, value: pool.set_target_percentage_electrolysis(
            int(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool numbers."""
    pools = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[PoolEntity] = []
    for pool_id, pool in pools.items():
        coordinator = coordinators[pool_id]
        for description in ENTITY_DESCRIPTIONS:
            entities.append(PoolNumberEntity(pool, coordinator, description))

    async_add_entities(entities)


class PoolNumberEntity(PoolEntity, NumberEntity):
    """Representation of a pool number entity."""

    entity_description: PoolstationNumberEntityDescription

    def __init__(
        self,
        pool: Pool,
        coordinator: PoolstationDataUpdateCoordinator,
        description: PoolstationNumberEntityDescription,
    ) -> None:
        """Initialize the pool's target PH."""
        super().__init__(pool, coordinator, " #{description.name}")
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator.pool)

    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        await self.entity_description.set_value_fn(self.coordinator.pool, value)
        self.async_write_ha_state()
