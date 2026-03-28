"""Tests for bchydro_export.client."""

from datetime import date
from pathlib import Path

from bchydro_export.client import _extract_bchydroparam, _portal_date

FIXTURES = Path(__file__).parent / "fixtures"


class TestExtractBchydroparam:
    def test_extracts_from_hidden_input(self):
        html = (FIXTURES / "login_success.html").read_text()
        assert _extract_bchydroparam(html) == "abc123-csrf-token-xyz"

    def test_extracts_from_span_fallback(self):
        html = '<span id="bchydroparam">span-token-456</span>'
        assert _extract_bchydroparam(html) == "span-token-456"

    def test_returns_empty_when_not_found(self):
        assert _extract_bchydroparam("<html><body>nothing</body></html>") == ""

    def test_extracts_from_single_quoted_attrs(self):
        html = "<input type='hidden' name='bchydroparam' value='single-quoted-tok' />"
        assert _extract_bchydroparam(html) == "single-quoted-tok"


class TestPortalDate:
    def test_formats_date_without_leading_zero(self):
        assert _portal_date(date(2026, 3, 1)) == "Mar 1, 2026"

    def test_formats_double_digit_day(self):
        assert _portal_date(date(2026, 3, 15)) == "Mar 15, 2026"

    def test_formats_december(self):
        assert _portal_date(date(2025, 12, 25)) == "Dec 25, 2025"


import requests_mock as rm

from bchydro_export import BCHydroExport
from bchydro_export.exceptions import BCHydroAuthError, BCHydroExportError
from bchydro_export.parser import ConsumptionReading


class TestBCHydroExportLogin:
    def test_successful_login_extracts_token(self):
        html = (FIXTURES / "login_success.html").read_text()
        with rm.Mocker() as m:
            m.post("https://app.bchydro.com/sso/UI/Login", text=html)
            client = BCHydroExport("test@example.com", "password123")
            session, token = client._login()
            assert token == "abc123-csrf-token-xyz"

    def test_login_failure_raises_auth_error(self):
        html = (FIXTURES / "login_failure.html").read_text()
        with rm.Mocker() as m:
            m.post("https://app.bchydro.com/sso/UI/Login", text=html)
            client = BCHydroExport("bad@example.com", "wrong")
            import pytest
            with pytest.raises(BCHydroAuthError):
                client._login()

    def test_login_token_fallback_to_download_centre(self):
        no_token_html = "<html><body>Welcome</body></html>"
        centre_html = (FIXTURES / "download_centre.html").read_text()
        with rm.Mocker() as m:
            m.post("https://app.bchydro.com/sso/UI/Login", text=no_token_html)
            m.get("https://app.bchydro.com/datadownload/web/download-centre.html", text=centre_html)
            client = BCHydroExport("test@example.com", "password123")
            session, token = client._login()
            assert token == "refreshed-csrf-token-999"


class TestBCHydroExportFetch:
    def _mock_full_flow(self, mocker, csv_text: str):
        login_html = (FIXTURES / "login_success.html").read_text()
        centre_html = (FIXTURES / "download_centre.html").read_text()
        mocker.post("https://app.bchydro.com/sso/UI/Login", text=login_html)
        mocker.get(rm.ANY, text=centre_html)
        mocker.post("https://app.bchydro.com/datadownload/web/validate-download-request.html", text="OK")
        mocker.post("https://app.bchydro.com/datadownload/web/create-download-request.html", text="OK")
        mocker.get(
            "https://app.bchydro.com/datadownload/web/download-file.html?requestId=recent",
            text=csv_text,
        )

    def test_fetch_csv_returns_raw_text(self):
        csv_text = (FIXTURES / "consumption.csv").read_text()
        with rm.Mocker() as m:
            self._mock_full_flow(m, csv_text)
            client = BCHydroExport("test@example.com", "pw")
            result = client.fetch_csv(date(2026, 3, 1), date(2026, 3, 5))
            assert "Net Consumption" in result

    def test_fetch_consumption_returns_readings(self):
        csv_text = (FIXTURES / "consumption.csv").read_text()
        with rm.Mocker() as m:
            self._mock_full_flow(m, csv_text)
            client = BCHydroExport("test@example.com", "pw")
            readings = client.fetch_consumption(date(2026, 3, 1), date(2026, 3, 5))
            assert len(readings) == 4
            assert all(isinstance(r, ConsumptionReading) for r in readings)

    def test_fetch_csv_chunking_for_large_range(self):
        csv_text = (FIXTURES / "consumption.csv").read_text()
        with rm.Mocker() as m:
            self._mock_full_flow(m, csv_text)
            client = BCHydroExport("test@example.com", "pw")
            client.fetch_csv(date(2026, 1, 1), date(2026, 3, 15))
            validate_calls = [
                h for h in m.request_history
                if "validate-download" in str(h.url)
            ]
            assert len(validate_calls) == 3

    def test_fetch_csv_export_failure_raises(self):
        login_html = (FIXTURES / "login_success.html").read_text()
        centre_html = (FIXTURES / "download_centre.html").read_text()
        with rm.Mocker() as m:
            m.post("https://app.bchydro.com/sso/UI/Login", text=login_html)
            m.get(rm.ANY, text=centre_html)
            m.post("https://app.bchydro.com/datadownload/web/validate-download-request.html", status_code=500)
            client = BCHydroExport("test@example.com", "pw")
            import pytest
            with pytest.raises(BCHydroExportError):
                client.fetch_csv(date(2026, 3, 1), date(2026, 3, 5))
