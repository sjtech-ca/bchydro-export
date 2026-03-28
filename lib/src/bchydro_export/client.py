"""BC Hydro data export client."""

from __future__ import annotations

import re
import time
from datetime import date, timedelta

import requests

from .exceptions import BCHydroAuthError, BCHydroExportError
from .parser import ConsumptionReading, parse_csv

_BASE = "https://app.bchydro.com"
_LOGIN_POST = f"{_BASE}/sso/UI/Login"
_LOGIN_GOTO = f"{_BASE}:443/BCHCustomerPortal/web/login.html"
_DOWNLOAD_CENTRE = f"{_BASE}/datadownload/web/download-centre.html"
_VALIDATE = f"{_BASE}/datadownload/web/validate-download-request.html"
_CREATE = f"{_BASE}/datadownload/web/create-download-request.html"
_DOWNLOAD_RECENT = f"{_BASE}/datadownload/web/download-file.html?requestId=recent"

_CHUNK_DAYS = 30
_CHUNK_PAUSE = 1  # seconds between chunk requests

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _extract_bchydroparam(html: str) -> str:
    """Extract the bchydroparam CSRF token from HTML.

    Checks hidden input fields first, then falls back to a span element.
    """
    m = re.search(
        r"<input[^>]+name=[\"']bchydroparam[\"'][^>]*value=[\"']([^\"']+)[\"']",
        html,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    m = re.search(
        r"<[^>]+id=[\"']bchydroparam[\"'][^>]*>([^<]+)<",
        html,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _portal_date(d: date) -> str:
    """Format a date as BC Hydro's portal expects: 'Mar 1, 2026' (no leading zero)."""
    return f"{d.strftime('%b')} {d.day}, {d.year}"


class BCHydroExport:
    """Fetch hourly consumption data from BC Hydro's Data Export portal.

    Args:
        email: BC Hydro account email.
        password: BC Hydro account password.
        user_agent: HTTP User-Agent string. Defaults to a Chrome browser UA.
            BC Hydro's WAF rejects non-browser user agents.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        email: str,
        password: str,
        user_agent: str = _DEFAULT_UA,
        timeout: int = 30,
    ):
        self._email = email
        self._password = password
        self._user_agent = user_agent
        self._timeout = timeout

    def _login(self) -> tuple[requests.Session, str]:
        """Authenticate and return (session, bchydroparam token)."""
        session = requests.Session()
        session.headers.update({"User-Agent": self._user_agent})

        resp = session.post(
            _LOGIN_POST,
            data={
                "realm": "bch-ps",
                "email": self._email,
                "password": self._password,
                "gotoUrl": _LOGIN_GOTO,
            },
            allow_redirects=True,
            timeout=self._timeout,
        )
        resp.raise_for_status()

        html = resp.text
        lower = html.lower()
        if 'name="email"' in lower and 'name="password"' in lower:
            raise BCHydroAuthError(
                "Still on login page after submit — bad credentials or blocked flow"
            )

        token = _extract_bchydroparam(html)
        if not token:
            centre_resp = session.get(
                _DOWNLOAD_CENTRE, allow_redirects=True, timeout=self._timeout
            )
            token = _extract_bchydroparam(centre_resp.text)

        if not token:
            raise BCHydroAuthError("Could not find bchydroparam token after login")

        return session, token

    def _export_chunk(
        self,
        session: requests.Session,
        token: str,
        from_date: date,
        to_date: date,
    ) -> tuple[str, str]:
        """Queue an export request and download the resulting CSV."""
        from_s = _portal_date(from_date)
        to_s = _portal_date(to_date)

        query = (
            f"?default=true&downloadType=CNSMPHSTRY&downloadFormat=CSVFILE"
            f"&downloadInterval=HOURLY&fromDate={from_s}&toDate={to_s}"
        )
        centre_resp = session.get(
            _DOWNLOAD_CENTRE + query, allow_redirects=True, timeout=self._timeout
        )
        refreshed = _extract_bchydroparam(centre_resp.text)
        if refreshed:
            token = refreshed

        headers = {
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": _BASE,
            "Referer": str(centre_resp.url),
            "X-CSRF-Token": token,
            "bchydroparam": token,
        }

        payload = {
            "accountId": "",
            "fromDate": from_s,
            "toDate": to_s,
            "downloadInterval": "HOURLY",
            "downloadType": "CONSUMPTION_HISTORY",
            "downloadFormat": "CSV_FILE",
        }

        validate_resp = session.post(
            _VALIDATE, data=payload, headers=headers, timeout=self._timeout
        )
        if validate_resp.status_code != 200:
            raise BCHydroExportError(
                f"Validate request failed with status {validate_resp.status_code}"
            )

        create_resp = session.post(
            _CREATE, data=payload, headers=headers, timeout=self._timeout
        )
        if create_resp.status_code != 200:
            raise BCHydroExportError(
                f"Create request failed with status {create_resp.status_code}"
            )

        download_resp = session.get(
            _DOWNLOAD_RECENT, allow_redirects=True, timeout=60
        )
        download_resp.raise_for_status()

        try:
            csv_text = download_resp.content.decode("utf-8")
        except UnicodeDecodeError:
            csv_text = download_resp.content.decode("ISO-8859-1", errors="replace")

        return csv_text, token

    def fetch_csv(self, from_date: date, to_date: date) -> str:
        """Fetch raw CSV text for a date range.

        Ranges exceeding 30 days are automatically split into chunks.
        """
        session, token = self._login()
        chunks: list[str] = []
        chunk_start = from_date

        while chunk_start <= to_date:
            chunk_end = min(to_date, chunk_start + timedelta(days=_CHUNK_DAYS - 1))
            csv_text, token = self._export_chunk(session, token, chunk_start, chunk_end)
            chunks.append(csv_text)
            chunk_start = chunk_end + timedelta(days=1)
            if chunk_start <= to_date:
                time.sleep(_CHUNK_PAUSE)

        if len(chunks) > 1:
            # Remove header row from subsequent chunks
            for i in range(1, len(chunks)):
                lines = chunks[i].splitlines()
                if len(lines) > 1:
                    chunks[i] = "\n".join(lines[1:])

        return "\n".join(chunks)

    def fetch_consumption(
        self, from_date: date, to_date: date
    ) -> list[ConsumptionReading]:
        """Fetch parsed consumption readings for a date range."""
        csv_text = self.fetch_csv(from_date, to_date)
        return parse_csv(csv_text)
