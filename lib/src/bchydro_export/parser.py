"""Parse BC Hydro CSV export data into ConsumptionReading objects."""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass

_ESTIMATED_TRUTHY = {"X", "Y", "TRUE", "1"}


@dataclass
class ConsumptionReading:
    """A single hourly consumption reading.

    Attributes:
        timestamp: Naive datetime in America/Vancouver local time.
        kwh: Net consumption in kilowatt-hours.
        estimated: True if BC Hydro flagged this as an estimated reading.
    """

    timestamp: dt.datetime
    kwh: float
    estimated: bool


def parse_csv(csv_text: str) -> list[ConsumptionReading]:
    """Parse BC Hydro CSV export text into a list of readings.

    Rows with missing timestamps or missing/unparseable consumption values
    are silently skipped.
    """
    readings: list[ConsumptionReading] = []
    reader = csv.DictReader(csv_text.splitlines())

    for row in reader:
        raw_ts = (row.get("Interval Start Date/Time") or "").strip()
        if not raw_ts:
            continue

        raw_kwh = (row.get("Net Consumption (kWh)") or "").strip()
        if not raw_kwh:
            continue
        try:
            kwh = float(raw_kwh)
        except ValueError:
            continue

        estimated = (row.get("Estimated Usage") or "").strip().upper() in _ESTIMATED_TRUTHY
        try:
            timestamp = dt.datetime.strptime(raw_ts, "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        readings.append(ConsumptionReading(timestamp=timestamp, kwh=kwh, estimated=estimated))

    return readings
