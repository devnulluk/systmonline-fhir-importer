from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class CredentialError(RuntimeError):
    """Raised without including credential values."""


@dataclass(frozen=True, repr=False)
class Credentials:
    username: str
    password: str

    def __repr__(self) -> str:
        return "Credentials(username=<redacted>, password=<redacted>)"


def _read_setting(name: str, environment: Mapping[str, str]) -> str:
    file_name = f"{name}_FILE"
    secret_path = environment.get(file_name, "").strip()
    direct_value = environment.get(name, "")

    if secret_path:
        try:
            value = Path(secret_path).read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise CredentialError(f"Unable to read the file configured by {file_name}") from error
        if not value:
            raise CredentialError(f"The file configured by {file_name} is empty")
        return value

    if direct_value:
        return direct_value
    raise CredentialError(f"Set {name}_FILE or {name}")


def load_credentials(environment: Mapping[str, str] | None = None) -> Credentials:
    """Load credentials with file-based secrets taking precedence over direct values."""
    values = os.environ if environment is None else environment
    return Credentials(
        username=_read_setting("SYSTMONLINE_USERNAME", values),
        password=_read_setting("SYSTMONLINE_PASSWORD", values),
    )
