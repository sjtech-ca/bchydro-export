"""Sensor entities for BC Hydro."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BCHydroCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BC Hydro sensors from a config entry."""
    coordinator: BCHydroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BCHydroYesterdaySensor(coordinator),
            BCHydroTotalSensor(coordinator),
            BCHydroLastUpdatedSensor(coordinator),
        ]
    )


class BCHydroYesterdaySensor(CoordinatorEntity[BCHydroCoordinator], SensorEntity):
    """Yesterday's total consumption."""

    _attr_name = "BC Hydro Yesterday Consumption"
    _attr_unique_id = "bchydro_yesterday_consumption"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("yesterday_kwh")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        return {"hourly": self.coordinator.data.get("yesterday_hourly", [])}


class BCHydroTotalSensor(CoordinatorEntity[BCHydroCoordinator], SensorEntity):
    """Cumulative total consumption for the Energy dashboard."""

    _attr_name = "BC Hydro Total Consumption"
    _attr_unique_id = "bchydro_total_consumption"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("cumulative_total")


class BCHydroLastUpdatedSensor(CoordinatorEntity[BCHydroCoordinator], SensorEntity):
    """When data was last fetched."""

    _attr_name = "BC Hydro Last Updated"
    _attr_unique_id = "bchydro_last_updated"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("last_updated")
