# bchydro-export

Fetch hourly electricity consumption data from [BC Hydro](https://www.bchydro.com/) (British Columbia's electric utility).

BC Hydro has no public API. This project scrapes the [Data Export](https://app.bchydro.com/datadownload/) portal to retrieve hourly consumption CSVs.

## Three ways to use it

| Package | For | Install |
|---------|-----|---------|
| [**bchydro-export**](lib/) | Python library — use anywhere | `pip install bchydro-export` |
| [**Pyscript app**](pyscript/) | Home Assistant via Pyscript | Copy file + pip install |
| [**HACS integration**](custom_components/bchydro/) | Home Assistant native integration | Install via HACS |

## Quick start (Python library)

```bash
pip install bchydro-export
```

```python
from datetime import date
from bchydro_export import BCHydroExport

client = BCHydroExport("email@example.com", "password")
readings = client.fetch_consumption(date(2026, 3, 1), date(2026, 3, 26))

for r in readings:
    print(f"{r.timestamp}  {r.kwh:.2f} kWh")
```

## Quick start (Home Assistant)

**Option A — HACS (recommended):**
Add this repo as a custom HACS repository, install, and configure via the UI.
See [HACS integration docs](custom_components/bchydro/).

**Option B — Pyscript:**
For lightweight setups using the Pyscript custom component.
See [Pyscript app docs](pyscript/).

## Security

BC Hydro recommends creating a **read-only secondary account** rather than using your primary credentials.

## Disclaimer

This project is not affiliated with BC Hydro. It scrapes a web portal, not an official API. BC Hydro may change their site at any time. Use at your own risk.

## License

MIT
