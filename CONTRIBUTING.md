# Contributing

## Development setup

```bash
git clone https://github.com/sammcj/bchydro-export.git
cd bchydro-export
python -m venv .venv
source .venv/bin/activate
pip install -e lib/
pip install -e ".[dev]"
```

## Running tests

```bash
# Library tests
pytest lib/tests/ -v

# All tests
pytest -v
```

## Project structure

- `lib/` — Standalone Python library (published to PyPI as `bchydro-export`)
- `pyscript/` — Home Assistant Pyscript app
- `custom_components/bchydro/` — HACS custom integration

## A note about BC Hydro's portal

This project scrapes BC Hydro's Data Export web portal. There is no official API.
BC Hydro may change their portal at any time, which can break the scraping logic.
If you encounter issues, the relevant code is in `lib/src/bchydro_export/client.py`.

Key things that have broken in the past:
- CSRF token (`bchydroparam`) location changes
- Session cookie requirements
- User-Agent filtering
- Date format expectations

## Tests

Library tests use recorded HTTP response fixtures in `lib/tests/fixtures/`.
These are redacted versions of real BC Hydro responses. If the portal changes,
update the fixtures to match.

Live integration tests are not run in CI (risk of account lockout). To smoke-test
with real credentials locally:

```bash
python -c "
from datetime import date, timedelta
from bchydro_export import BCHydroExport
client = BCHydroExport('your-email', 'your-password')
yesterday = date.today() - timedelta(days=1)
readings = client.fetch_consumption(yesterday, yesterday)
print(f'Got {len(readings)} readings')
for r in readings[:3]:
    print(f'  {r.timestamp} {r.kwh:.3f} kWh')
"
```
