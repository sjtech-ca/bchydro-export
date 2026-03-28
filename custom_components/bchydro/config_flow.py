"""Config flow for BC Hydro integration."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .client import BCHydroExport
from .exceptions import BCHydroAuthError

from .const import DEFAULT_LOOKBACK_DAYS, DEFAULT_SCAN_HOUR, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required("email"): str,
        vol.Required("password"): str,
    }
)


class BCHydroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BC Hydro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = BCHydroExport(user_input["email"], user_input["password"])
                yesterday = date.today() - timedelta(days=1)
                await self.hass.async_add_executor_job(
                    client.fetch_consumption, yesterday, yesterday
                )
            except BCHydroAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input["email"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input["email"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BCHydroOptionsFlow(config_entry)


class BCHydroOptionsFlow(OptionsFlow):
    """Handle options for BC Hydro."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show menu: settings or backfill."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "backfill"],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "lookback_days",
                        default=self._config_entry.options.get(
                            "lookback_days", DEFAULT_LOOKBACK_DAYS
                        ),
                    ): vol.All(int, vol.Range(min=1, max=365)),
                    vol.Optional(
                        "scan_hour",
                        default=self._config_entry.options.get(
                            "scan_hour", DEFAULT_SCAN_HOUR
                        ),
                    ): vol.All(int, vol.Range(min=0, max=23)),
                }
            ),
        )

    async def async_step_backfill(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            from_date = user_input["from_date"]
            to_date = user_input["to_date"]

            # Selector returns date objects, but handle strings too
            if isinstance(from_date, str):
                from_date = date.fromisoformat(from_date)
            if isinstance(to_date, str):
                to_date = date.fromisoformat(to_date)

            coordinator = self.hass.data[DOMAIN].get(self._config_entry.entry_id)
            if coordinator is None:
                return self.async_abort(reason="not_loaded")

            try:
                count = await coordinator.async_backfill(from_date, to_date)
            except Exception as err:
                return self.async_abort(
                    reason="backfill_failed",
                    description_placeholders={"error": str(err)},
                )

            return self.async_abort(
                reason="backfill_complete",
                description_placeholders={"count": str(count), "from": str(from_date), "to": str(to_date)},
            )

        from homeassistant.helpers.selector import (
            DateSelector,
            DateSelectorConfig,
        )

        default_from = str(date.today() - timedelta(days=365))
        default_to = str(date.today() - timedelta(days=1))

        return self.async_show_form(
            step_id="backfill",
            data_schema=vol.Schema(
                {
                    vol.Required("from_date", default=default_from): DateSelector(
                        DateSelectorConfig()
                    ),
                    vol.Required("to_date", default=default_to): DateSelector(
                        DateSelectorConfig()
                    ),
                }
            ),
        )
