# BC Hydro Pyscript App

A [Pyscript](https://github.com/custom-components/pyscript) app that fetches BC Hydro
consumption data and imports it into Home Assistant's long-term statistics and Energy dashboard.

## Prerequisites

- Home Assistant with [Pyscript](https://github.com/custom-components/pyscript) installed
- `bchydro-export` Python library installed in your HA environment:
  ```bash
  pip install bchydro-export
  ```

## Install

1. Copy `bchydro_export.py` to `/config/pyscript/`

2. Add the required helpers and config to your `configuration.yaml`
   (see [examples/configuration.yaml](examples/configuration.yaml)):

   - `input_number.bchydro_total_kwh_store` — persists cumulative total
   - `input_text.bchydro_last_processed_date` — tracks last processed date
   - Template sensor for Energy dashboard
   - Pyscript app config with credentials
   - Daily automation trigger

3. Add your credentials to `secrets.yaml`:
   ```yaml
   bchydro_email: "your-email@example.com"
   bchydro_password: "your-password"
   ```

4. Restart Home Assistant

## Services

### `pyscript.bchydro_update`

Fetches consumption data for the configured lookback window (default 35 days).
Writes hourly and cumulative statistics. Updates `sensor.bchydro_yesterday_kwh`.

Call with optional `days` parameter to override the lookback window.

### `pyscript.bchydro_backfill`

One-time backfill from a specific date. Rebuilds cumulative totals from scratch.

```yaml
service: pyscript.bchydro_backfill
data:
  from_date: "2025-01-01"
```

## Energy Dashboard Setup

After the first successful update, add `bchydro:total_kwh` as an energy source
in Settings → Dashboards → Energy → Electricity Grid → Add Consumption.

## Errors

Errors are reported via persistent notifications in the HA UI.
