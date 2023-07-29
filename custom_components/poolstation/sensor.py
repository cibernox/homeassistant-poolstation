"""Support for Poolstation sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pypoolstation import Pool

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity


@dataclass
class PoolstationEntityDescriptionMixin:
    """Mixin values for Poolstation entities."""

    value_fn: Callable[[Pool], int | str]


@dataclass
class PoolstationSensorEntityDescription(
    SensorEntityDescription, PoolstationEntityDescriptionMixin
):
    """Class describing Poolstation sensor entities."""

    has_fn: Callable[[Pool], bool] = lambda _: True


ENTITY_DESCRIPTIONS = (
    PoolstationSensorEntityDescription(
        key="pH",
        name="pH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pool: pool.current_ph,
        has_fn=lambda pool: pool.current_ph is not None,
    ),
    PoolstationSensorEntityDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:coolant-temperature",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda pool: pool.temperature,
        has_fn=lambda pool: pool.temperature is not None,
    ),
    PoolstationSensorEntityDescription(
        key="salt_concentration",
        name="Salt Concentration",
        icon="mdi:shaker",
        native_unit_of_measurement="gr/l",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pool: pool.salt_concentration,
        has_fn=lambda pool: pool.salt_concentration is not None,
    ),
    PoolstationSensorEntityDescription(
        key="percentage_electrolysis",
        name="Electrolysis",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=lambda pool: pool.percentage_electrolysis,
        has_fn=lambda pool: pool.percentage_electrolysis is not None,
    ),
    PoolstationSensorEntityDescription(
        key="current_orp",
        name="ORP",
        icon="mdi:atom",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=lambda pool: pool.current_orp,
        has_fn=lambda pool: pool.current_orp is not None,
    ),
    PoolstationSensorEntityDescription(
        key="free_chlorine",
        name="Chlorine",
        icon="mdi:cup-water",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ppm",
        value_fn=lambda pool: pool.current_clppm,
        has_fn=lambda pool: pool.current_clppm is not None,
    ),
)


class PoolSensorEntity(PoolEntity, SensorEntity):
    """Representation of a pool sensor."""

    entity_description: PoolstationSensorEntityDescription

    def __init__(
        self,
        pool: Pool,
        coordinator: PoolstationDataUpdateCoordinator,
        description: PoolstationSensorEntityDescription,
    ) -> None:
        """Initialize the pool's target PH."""
        super().__init__(pool, coordinator, " #{description.name}")
        self.entity_description = description

    @property
    def native_value(self) -> str | int:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.pool)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the poolstation sensors."""
    stations = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[PoolEntity] = []
    for pool_id, pool in stations.items():
        coordinator = coordinators[pool_id]
        for description in ENTITY_DESCRIPTIONS:
            entities.append(PoolSensorEntity(pool, coordinator, description))

    async_add_entities(entities)
