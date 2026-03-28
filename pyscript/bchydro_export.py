"""BC Hydro → Home Assistant via Pyscript.

Fetches hourly consumption CSVs from BC Hydro and imports them into
Home Assistant long-term statistics for the Energy dashboard.

Prerequisites:
- pip install bchydro-export (in the HA Python environment)
- pyscript integration with allow_all_imports: true

Configuration (configuration.yaml):
  pyscript:
    allow_all_imports: true
    apps:
      bchydro:
        email: !secret bchydro_email
        password: !secret bchydro_password
        days: 35

Required helpers (create in HA UI or YAML):
- input_number.bchydro_total_kwh_store (min 0, max 999999, step 0.001)
- input_text.bchydro_last_processed_date
"""

from __future__ import annotations

import datetime as dt

from homeassistant.components.recorder.models.statistics import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics


def _app_cfg() -> dict:
    apps = (pyscript.config or {}).get("apps", {})
    return apps.get("bchydro", {}) if isinstance(apps, dict) else {}


def _get_tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/Vancouver")


def _notify_error(title: str, message: str):
    service.call(
        "persistent_notification",
        "create",
        title=title,
        message=message,
        notification_id="bchydro_error",
    )


def _fetch_readings(email: str, password: str, from_date: dt.date, to_date: dt.date):
    """Run the sync library in an executor thread."""
    from bchydro_export import BCHydroExport
    client = BCHydroExport(email, password)
    return task.executor(client.fetch_consumption, from_date, to_date)


def _import_hourly_stats(readings):
    """Write hourly interval statistics (bchydro:hourly_kwh)."""
    tz = _get_tz()
    metadata = StatisticMetaData(
        statistic_id="bchydro:hourly_kwh",
        name="BC Hydro Hourly Consumption",
        source="bchydro",
        unit_of_measurement="kWh",
        unit_class="energy",
        mean_type=StatisticMeanType.NONE,
        has_sum=False,
    )
    stats = []
    for r in readings:
        start = r.timestamp.replace(tzinfo=tz).astimezone(dt.timezone.utc)
        stats.append({"start": start, "state": float(r.kwh)})

    for i in range(0, len(stats), 500):
        async_add_external_statistics(hass, metadata, stats[i : i + 500])


def _import_cumulative_stats(readings, base_total: float) -> float:
    """Write cumulative total statistics (bchydro:total_kwh) for Energy dashboard.

    Returns the final cumulative total.
    """
    tz = _get_tz()
    metadata = StatisticMetaData(
        statistic_id="bchydro:total_kwh",
        name="BC Hydro Total kWh",
        source="bchydro",
        unit_of_measurement="kWh",
        unit_class="energy",
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
    )
    sorted_readings = sorted(readings, key=lambda r: r.timestamp)
    total = float(base_total)
    stats = []
    for r in sorted_readings:
        total += float(r.kwh)
        start = r.timestamp.replace(tzinfo=tz).astimezone(dt.timezone.utc)
        stats.append({"start": start, "state": total, "sum": total})

    for i in range(0, len(stats), 500):
        async_add_external_statistics(hass, metadata, stats[i : i + 500])

    return total


def _get_stored_total() -> float:
    try:
        val = state.get("input_number.bchydro_total_kwh_store")
    except NameError:
        return 0.0
    if val in (None, "", "unknown", "unavailable"):
        return 0.0
    return float(val)


def _set_stored_total(total: float):
    service.call(
        "input_number",
        "set_value",
        entity_id="input_number.bchydro_total_kwh_store",
        value=round(total, 3),
    )


def _get_last_processed_date() -> str:
    try:
        val = state.get("input_text.bchydro_last_processed_date")
    except NameError:
        return ""
    if val in (None, "unknown", "unavailable"):
        return ""
    return val.strip()


def _set_last_processed_date(date_str: str):
    service.call(
        "input_text",
        "set_value",
        entity_id="input_text.bchydro_last_processed_date",
        value=date_str,
    )


@service
async def bchydro_update(days: int | None = None):
    """Fetch recent BC Hydro data and import into HA statistics."""
    cfg = _app_cfg()
    email = cfg.get("email")
    password = cfg.get("password")
    if not email or not password:
        _notify_error("BC Hydro", "Missing email/password in pyscript.apps.bchydro config")
        return

    tz = _get_tz()
    now = dt.datetime.now(tz)
    yesterday = now.date() - dt.timedelta(days=1)
    lookback = int(days or cfg.get("days") or 35)
    from_date = yesterday - dt.timedelta(days=lookback - 1)

    try:
        readings = _fetch_readings(email, password, from_date, yesterday)
    except Exception as e:
        _notify_error("BC Hydro", f"Fetch failed: {type(e).__name__}: {e}")
        return

    # Import hourly stats (full range)
    try:
        _import_hourly_stats(readings)
    except Exception as e:
        _notify_error("BC Hydro", f"Hourly stats import failed: {e}")

    # Yesterday summary sensor
    yesterday_readings = [r for r in readings if r.timestamp.date() == yesterday]
    yesterday_total = sum(r.kwh for r in yesterday_readings)
    hourly_detail = [
        {"t": r.timestamp.strftime("%H:%M"), "kwh": round(r.kwh, 3), "est": r.estimated}
        for r in sorted(yesterday_readings, key=lambda r: r.timestamp)
    ]
    state.set(
        "sensor.bchydro_yesterday_kwh",
        round(yesterday_total, 3),
        {
            "unit_of_measurement": "kWh",
            "hourly": hourly_detail,
            "estimated_intervals": sum(1 for r in yesterday_readings if r.estimated),
            "fetched_at": now.isoformat(),
        },
    )

    # Cumulative total for Energy dashboard
    yesterday_str = yesterday.isoformat()
    last_processed = _get_last_processed_date()

    if last_processed != yesterday_str:
        prev_total = _get_stored_total()
        new_total = prev_total + yesterday_total
        _set_stored_total(new_total)
        _set_last_processed_date(yesterday_str)

        try:
            _import_cumulative_stats(yesterday_readings, prev_total)
        except Exception as e:
            _notify_error("BC Hydro", f"Cumulative stats import failed: {e}")


@service
async def bchydro_backfill(from_date: str | None = None):
    """Backfill BC Hydro data from a given date. Rebuilds cumulative totals.

    Args:
        from_date: Start date as YYYY-MM-DD string. Fetches up to yesterday.
    """
    cfg = _app_cfg()
    email = cfg.get("email")
    password = cfg.get("password")
    if not email or not password:
        _notify_error("BC Hydro", "Missing email/password in pyscript.apps.bchydro config")
        return

    if not from_date:
        _notify_error("BC Hydro", "bchydro_backfill requires from_date (YYYY-MM-DD)")
        return

    tz = _get_tz()
    now = dt.datetime.now(tz)
    yesterday = now.date() - dt.timedelta(days=1)
    start = dt.date.fromisoformat(str(from_date))

    try:
        readings = _fetch_readings(email, password, start, yesterday)
    except Exception as e:
        _notify_error("BC Hydro", f"Backfill fetch failed: {type(e).__name__}: {e}")
        return

    try:
        _import_hourly_stats(readings)
    except Exception as e:
        _notify_error("BC Hydro", f"Hourly stats import failed: {e}")

    try:
        end_total = _import_cumulative_stats(readings, 0.0)
        _set_stored_total(end_total)
        _set_last_processed_date(yesterday.isoformat())
    except Exception as e:
        _notify_error("BC Hydro", f"Cumulative stats import failed: {e}")
