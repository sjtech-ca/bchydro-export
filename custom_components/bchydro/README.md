# BC Hydro — HACS Integration

A Home Assistant custom integration that fetches hourly electricity consumption
from BC Hydro and exposes it for the Energy dashboard.

## Install via HACS

1. Open HACS → Integrations → Custom Repositories
2. Add `https://github.com/sjtech-ca/bchydro-export` as an Integration
3. Install "BC Hydro"
4. Restart Home Assistant

## Setup

1. Go to Settings → Devices & Services → Add Integration → "BC Hydro"
2. Enter your BC Hydro email and password
3. The integration creates three sensors:
   - **BC Hydro Yesterday Consumption** — yesterday's total kWh with hourly breakdown
   - **BC Hydro Total Consumption** — cumulative total (for Energy dashboard)
   - **BC Hydro Last Updated** — last successful fetch timestamp

## Energy Dashboard

After setup, go to Settings → Dashboards → Energy → Electricity Grid → Add Consumption
and select **BC Hydro Total Consumption**.

You can also add **bchydro:total_kwh** from the external statistics if you prefer
the statistics-based approach.

## Options

Go to the integration's options to configure:
- **Lookback days** (default: 35) — how many days of data to fetch each update
- **Daily update hour** (default: 9) — when to fetch new data (BC Hydro data is delayed ~24h)

## Security Note

BC Hydro recommends creating a read-only secondary account for third-party access.
Credentials are stored in Home Assistant's encrypted config entry storage.
