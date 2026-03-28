"""DataUpdateCoordinator for BC Hydro."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.components.recorder.models.statistics import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics

from .client import BCHydroExport
from .exceptions import BCHydroAuthError, BCHydroExportError

from .const import DEFAULT_LOOKBACK_DAYS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.totals"


class BCHydroCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches BC Hydro data daily."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=dt.timedelta(hours=24),
        )
        self._email = entry.data["email"]
        self._password = entry.data["password"]
        self._lookback = entry.options.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._cumulative_total: float = 0.0
        self._last_processed_date: str = ""

    async def async_load_stored_totals(self) -> None:
        """Load persisted cumulative total from storage."""
        data = await self._store.async_load()
        if data:
            self._cumulative_total = float(data.get("cumulative_total", 0.0))
            self._last_processed_date = data.get("last_processed_date", "")

    async def _async_save_totals(self) -> None:
        await self._store.async_save(
            {
                "cumulative_total": self._cumulative_total,
                "last_processed_date": self._last_processed_date,
            }
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from BC Hydro."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Vancouver")
        now = dt.datetime.now(tz)
        yesterday = now.date() - dt.timedelta(days=1)
        from_date = yesterday - dt.timedelta(days=self._lookback - 1)

        try:
            client = BCHydroExport(self._email, self._password)
            readings = await self.hass.async_add_executor_job(
                client.fetch_consumption, from_date, yesterday
            )
        except BCHydroAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BCHydroExportError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        # Import hourly statistics
        hourly_meta = StatisticMetaData(
            statistic_id="bchydro:hourly_kwh",
            name="BC Hydro Hourly Consumption",
            source="bchydro",
            unit_of_measurement="kWh",
            unit_class="energy",
            mean_type=StatisticMeanType.NONE,
            has_sum=False,
        )
        hourly_stats = []
        for r in readings:
            start = r.timestamp.replace(tzinfo=tz).astimezone(dt.timezone.utc)
            hourly_stats.append({"start": start, "state": float(r.kwh)})

        for i in range(0, len(hourly_stats), 500):
            async_add_external_statistics(
                self.hass, hourly_meta, hourly_stats[i : i + 500]
            )

        # Yesterday summary
        yesterday_readings = [r for r in readings if r.timestamp.date() == yesterday]
        yesterday_kwh = sum(r.kwh for r in yesterday_readings)
        yesterday_hourly = [
            {"t": r.timestamp.strftime("%H:%M"), "kwh": round(r.kwh, 3)}
            for r in sorted(yesterday_readings, key=lambda r: r.timestamp)
        ]

        # Cumulative total
        yesterday_str = yesterday.isoformat()
        if self._last_processed_date != yesterday_str:
            self._cumulative_total += yesterday_kwh
            self._last_processed_date = yesterday_str

            # Write cumulative statistics
            cum_meta = StatisticMetaData(
                statistic_id="bchydro:total_kwh",
                name="BC Hydro Total kWh",
                source="bchydro",
                unit_of_measurement="kWh",
                unit_class="energy",
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
            )
            total = self._cumulative_total - yesterday_kwh
            cum_stats = []
            for r in sorted(yesterday_readings, key=lambda r: r.timestamp):
                total += float(r.kwh)
                start = r.timestamp.replace(tzinfo=tz).astimezone(dt.timezone.utc)
                cum_stats.append({"start": start, "state": total, "sum": total})

            for i in range(0, len(cum_stats), 500):
                async_add_external_statistics(
                    self.hass, cum_meta, cum_stats[i : i + 500]
                )

            await self._async_save_totals()

        return {
            "yesterday_kwh": round(yesterday_kwh, 3),
            "yesterday_hourly": yesterday_hourly,
            "cumulative_total": round(self._cumulative_total, 3),
            "last_updated": now.isoformat(),
        }

    async def async_backfill(self, from_date: dt.date, to_date: dt.date) -> int:
        """Backfill historical data for a date range.

        Fetches consumption data, writes hourly and cumulative statistics,
        and updates the persistent total. Returns the number of readings imported.
        """
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Vancouver")

        try:
            client = BCHydroExport(self._email, self._password)
            readings = await self.hass.async_add_executor_job(
                client.fetch_consumption, from_date, to_date
            )
        except BCHydroAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (BCHydroExportError, Exception) as err:
            raise UpdateFailed(str(err)) from err

        if not readings:
            return 0

        # Import hourly statistics
        hourly_meta = StatisticMetaData(
            statistic_id="bchydro:hourly_kwh",
            name="BC Hydro Hourly Consumption",
            source="bchydro",
            unit_of_measurement="kWh",
            unit_class="energy",
            mean_type=StatisticMeanType.NONE,
            has_sum=False,
        )
        hourly_stats = []
        for r in readings:
            start = r.timestamp.replace(tzinfo=tz).astimezone(dt.timezone.utc)
            hourly_stats.append({"start": start, "state": float(r.kwh)})

        for i in range(0, len(hourly_stats), 500):
            async_add_external_statistics(
                self.hass, hourly_meta, hourly_stats[i : i + 500]
            )

        # Rebuild cumulative statistics from scratch for the backfill range
        cum_meta = StatisticMetaData(
            statistic_id="bchydro:total_kwh",
            name="BC Hydro Total kWh",
            source="bchydro",
            unit_of_measurement="kWh",
            unit_class="energy",
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
        )
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        total = 0.0
        cum_stats = []
        for r in sorted_readings:
            total += float(r.kwh)
            start = r.timestamp.replace(tzinfo=tz).astimezone(dt.timezone.utc)
            cum_stats.append({"start": start, "state": total, "sum": total})

        for i in range(0, len(cum_stats), 500):
            async_add_external_statistics(
                self.hass, cum_meta, cum_stats[i : i + 500]
            )

        # Update persistent totals
        self._cumulative_total = total
        self._last_processed_date = to_date.isoformat()
        await self._async_save_totals()

        # Refresh sensor data
        await self.async_request_refresh()

        return len(readings)
