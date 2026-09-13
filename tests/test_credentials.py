from pathlib import Path

import pytest

from systmonline_fhir.credentials import CredentialError, load_credentials


def test_loads_direct_environment_values():
    credentials = load_credentials(
        {"SYSTMONLINE_USERNAME": "person", "SYSTMONLINE_PASSWORD": "example-password"}
    )

    assert credentials.username == "person"
    assert credentials.password == "example-password"
    assert "person" not in repr(credentials)
    assert "example-password" not in repr(credentials)


def test_secret_files_take_precedence_and_trim_only_line_endings(tmp_path: Path):
    username = tmp_path / "username"
    password = tmp_path / "password"
    username.write_text("file-person\n", encoding="utf-8")
    password.write_text(" password with spaces \r\n", encoding="utf-8")

    credentials = load_credentials(
        {
            "SYSTMONLINE_USERNAME": "ignored-person",
            "SYSTMONLINE_PASSWORD": "ignored-password",
            "SYSTMONLINE_USERNAME_FILE": str(username),
            "SYSTMONLINE_PASSWORD_FILE": str(password),
        }
    )

    assert credentials.username == "file-person"
    assert credentials.password == " password with spaces "


@pytest.mark.parametrize("missing", ["SYSTMONLINE_USERNAME", "SYSTMONLINE_PASSWORD"])
def test_missing_setting_fails_without_disclosing_other_value(missing: str):
    environment = {
        "SYSTMONLINE_USERNAME": "private-user",
        "SYSTMONLINE_PASSWORD": "private-password",
    }
    del environment[missing]

    with pytest.raises(CredentialError) as caught:
        load_credentials(environment)

    assert "private-user" not in str(caught.value)
    assert "private-password" not in str(caught.value)


def test_unreadable_secret_does_not_fall_back_to_direct_value(tmp_path: Path):
    missing = tmp_path / "missing-secret"

    with pytest.raises(CredentialError, match="SYSTMONLINE_PASSWORD_FILE"):
        load_credentials(
            {
                "SYSTMONLINE_USERNAME": "person",
                "SYSTMONLINE_PASSWORD": "must-not-be-used",
                "SYSTMONLINE_PASSWORD_FILE": str(missing),
            }
        )
