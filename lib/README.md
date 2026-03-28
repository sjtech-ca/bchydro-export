# bchydro-export

Fetch hourly electricity consumption data from BC Hydro's Data Export portal.

BC Hydro has no public API. This library screen-scrapes the [Data Export](https://app.bchydro.com/datadownload/) portal to download hourly CSV data and parse it into Python objects.

## Install

```bash
pip install bchydro-export
```

## Usage

```python
from datetime import date
from bchydro_export import BCHydroExport

client = BCHydroExport("your-email@example.com", "your-password")

# Get parsed consumption readings
readings = client.fetch_consumption(
    from_date=date(2026, 3, 1),
    to_date=date(2026, 3, 26),
)

for r in readings:
    print(f"{r.timestamp}  {r.kwh:.2f} kWh  {'(estimated)' if r.estimated else ''}")

# Or get the raw CSV text
csv_text = client.fetch_csv(from_date=date(2026, 3, 1), to_date=date(2026, 3, 26))
```

## API

### `BCHydroExport(email, password, user_agent=..., timeout=30)`

- `fetch_consumption(from_date, to_date)` → `list[ConsumptionReading]`
- `fetch_csv(from_date, to_date)` → `str`

Date ranges longer than 30 days are automatically split into chunks.

### `ConsumptionReading`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | Naive, local to America/Vancouver |
| `kwh` | `float` | Net consumption |
| `estimated` | `bool` | True if BC Hydro flagged as estimated |

### Exceptions

- `BCHydroAuthError` — login failed (bad credentials, CAPTCHA, or MFA)
- `BCHydroExportError` — export request or download failed

## Security Note

BC Hydro recommends creating a **read-only secondary account** rather than using your primary credentials. This library stores nothing — credentials are only used for the HTTP session during a `fetch_*` call.

## BC Hydro's Portal

This library scrapes a web portal, not an official API. If BC Hydro changes their site, things may break. Please open an issue if you encounter problems.

## License

MIT
