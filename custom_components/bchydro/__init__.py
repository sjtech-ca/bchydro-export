"""BC Hydro integration for Home Assistant."""

from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import BCHydroCoordinator

PLATFORMS = [Platform.SENSOR]

SERVICE_BACKFILL = "backfill"
SERVICE_BACKFILL_SCHEMA = vol.Schema(
    {
        vol.Required("from_date"): cv.date,
        vol.Required("to_date"): cv.date,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BC Hydro from a config entry."""
    coordinator = BCHydroCoordinator(hass, entry)
    await coordinator.async_load_stored_totals()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def handle_backfill(call: ServiceCall) -> None:
        """Handle the backfill service call."""
        from_date = call.data["from_date"]
        to_date = call.data["to_date"]
        # Use the first (only) coordinator
        from homeassistant.components.persistent_notification import async_create
        for coord in hass.data[DOMAIN].values():
            count = await coord.async_backfill(from_date, to_date)
            async_create(
                hass,
                f"Imported {count} readings from {from_date} to {to_date}",
                title="BC Hydro Backfill Complete",
                notification_id="bchydro_backfill",
            )
            break

    if not hass.services.has_service(DOMAIN, SERVICE_BACKFILL):
        hass.services.async_register(
            DOMAIN, SERVICE_BACKFILL, handle_backfill, schema=SERVICE_BACKFILL_SCHEMA
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BC Hydro config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_BACKFILL)
    return unload_ok
