"""BC Hydro export exceptions."""


class BCHydroError(Exception):
    """Base exception for bchydro-export."""


class BCHydroAuthError(BCHydroError):
    """Login failed — bad credentials, CAPTCHA challenge, or MFA block."""


class BCHydroExportError(BCHydroError):
    """Export request or CSV download failed."""
