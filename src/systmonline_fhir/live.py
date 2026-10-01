from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .capture import CaptureError, Response, SessionExpired, _is_login_page
from .credentials import Credentials


class LiveTransport(Protocol):
    def get(self, url: str) -> Response: ...
    def post(self, url: str, data: dict[str, str]) -> Response: ...


class RequestsTransport:
    def __init__(self, *, timeout: float = 60) -> None:
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers["User-Agent"] = "systmonline-fhir-importer/0.7"

    @staticmethod
    def _response(response: requests.Response) -> Response:
        return Response(
            response.url,
            response.status_code,
            response.headers.get("content-type", "application/octet-stream"),
            response.content,
        )

    def get(self, url: str) -> Response:
        return self._response(self.session.get(url, timeout=self.timeout))

    def post(self, url: str, data: dict[str, str]) -> Response:
        return self._response(self.session.post(url, data=data, timeout=self.timeout))


@dataclass(frozen=True)
class SavedPage:
    kind: str
    sequence: int
    sha256: str
    byte_count: int
    captured_at: str
    filename: str
    window_start: str | None = None
    window_end: str | None = None


def historical_windows(start: date, end: date, days: int = 60) -> list[tuple[date, date]]:
    """Return inclusive, non-overlapping windows, newest first."""
    if days < 1:
        raise ValueError("days must be positive")
    if start > end:
        raise ValueError("start must not be after end")
    windows: list[tuple[date, date]] = []
    cursor = end
    while cursor >= start:
        window_start = max(start, cursor - timedelta(days=days - 1))
        windows.append((window_start, cursor))
        cursor = window_start - timedelta(days=1)
    return windows


def _fields(form: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for control in form.select("input[name], select[name], textarea[name]"):
        name = str(control.get("name"))
        kind = str(control.get("type", "")).lower()
        if kind in {"submit", "button", "image", "file"}:
            continue
        if kind in {"checkbox", "radio"} and not control.has_attr("checked"):
            continue
        if control.name == "select":
            selected = control.select_one("option[selected]") or control.select_one("option")
            values[name] = str(selected.get("value", "")) if selected else ""
        else:
            values[name] = str(control.get("value", ""))
    return values


def _form(soup: BeautifulSoup, action: str, required: str | None = None) -> Tag:
    for candidate in soup.select("form[action]"):
        if str(candidate.get("action", "")).rstrip("/").endswith(action) and (
            required is None or candidate.select_one(f'[name="{required}"]')
        ):
            return candidate
    raise CaptureError(f"SystmOnline response did not contain the expected {action} form")


def _page_count(body: bytes, heading: str) -> int:
    text = BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
    match = re.search(rf"{re.escape(heading)}\s*\(Page\s+\d+/(\d+)\)", text, re.IGNORECASE)
    return int(match.group(1)) if match else 1


class SystmOnlineClient:
    def __init__(
        self,
        base_url: str,
        transport: LiveTransport,
        destination: Path,
        *,
        delay_seconds: float = 1.0,
        sleep=time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.transport = transport
        self.destination = destination
        self.delay_seconds = delay_seconds
        self.sleep = sleep
        self.pages: list[SavedPage] = []
        self.destination.mkdir(parents=True, exist_ok=True)

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    def _check(self, response: Response) -> Response:
        if response.status != 200:
            raise CaptureError(f"SystmOnline returned HTTP {response.status}")
        if _is_login_page(response):
            raise SessionExpired("SystmOnline session is not authenticated or has expired")
        return response

    def login(self, credentials: Credentials) -> Response:
        # The first request establishes the cookie required by the login form.
        self.transport.get(self._url("Login?Redir=1"))
        login_page = self.transport.get(self._url("Login"))
        soup = BeautifulSoup(login_page.body, "html.parser")
        form = _form(soup, "Login", "Username")
        data = _fields(form)
        data.update({"Username": credentials.username, "Password": credentials.password, "Login": ""})
        response = self.transport.post(urljoin(login_page.url, str(form.get("action"))), data)
        return self._check(response)

    def _post(self, path: str, data: dict[str, str]) -> Response:
        if self.delay_seconds:
            self.sleep(self.delay_seconds)
        return self._check(self.transport.post(self._url(path), data))

    def _save(
        self,
        response: Response,
        kind: str,
        sequence: int,
        *,
        window: tuple[date, date] | None = None,
    ) -> Path:
        digest = sha256(response.body).hexdigest()
        filename = f"{kind}-{sequence:04d}-{digest[:12]}.html"
        path = self.destination / filename
        path.write_bytes(response.body)
        saved = SavedPage(
            kind,
            sequence,
            digest,
            len(response.body),
            datetime.now(UTC).isoformat(),
            filename,
            window[0].isoformat() if window else None,
            window[1].isoformat() if window else None,
        )
        self.pages.append(saved)
        self.write_manifest(complete=False)
        return path

    def _menu_form(self, page: Response, action: str, label: str) -> dict[str, str]:
        soup = BeautifulSoup(page.body, "html.parser")
        form = _form(soup, action)
        data = _fields(form)
        data[label] = data.get(label, "")
        return data

    def capture_patient_record(self, menu: Response, start: date, end: date) -> list[Path]:
        landing = self._post("PatientRecord", self._menu_form(menu, "PatientRecord", "Patient Record"))
        form = _form(BeautifulSoup(landing.body, "html.parser"), "PatientRecord", "DateFrom")
        filters = _fields(form)
        filters.update(
            {
                "DateFrom": start.strftime("%d/%m/%Y"),
                "DateTo": end.strftime("%d/%m/%Y"),
                "IncludeUnknownDates": "on",
                "Search": "",
                "TextSearch": "",
            }
        )
        first = self._post("PatientRecord", filters)
        count = _page_count(first.body, "Patient Record")
        paths = [self._save(first, "patient-record-page", 1)]
        for number in range(2, count + 1):
            data = dict(filters)
            data[f"Page{number}"] = f"Page{number}"
            paths.append(self._save(self._post("PatientRecord", data), "patient-record-page", number))
        return paths

    def capture_test_results(
        self, menu: Response, start: date, end: date, *, window_days: int = 60
    ) -> list[tuple[list[Path], list[Path]]]:
        landing = self._post(
            "ViewTestResults", self._menu_form(menu, "ViewTestResults", "View Test Results")
        )
        base_form = _form(BeautifulSoup(landing.body, "html.parser"), "ViewTestResults", "ResultsFrom")
        base = _fields(base_form)
        captured: list[tuple[list[Path], list[Path]]] = []
        index_sequence = detail_sequence = 0
        for window in historical_windows(start, end, window_days):
            filters = dict(base)
            filters.update(
                {
                    "ResultsFrom": window[0].strftime("%d/%m/%Y"),
                    "ResultsTo": window[1].strftime("%d/%m/%Y"),
                    "Search": "",
                }
            )
            first = self._post("ViewTestResults", filters)
            responses = [first]
            for number in range(2, _page_count(first.body, "Test Results") + 1):
                data = dict(filters)
                data[f"Page{number}"] = f"Page{number}"
                responses.append(self._post("ViewTestResults", data))

            index_paths: list[Path] = []
            detail_paths: list[Path] = []
            for response in responses:
                index_sequence += 1
                index_paths.append(
                    self._save(response, "test-results-page", index_sequence, window=window)
                )
                soup = BeautifulSoup(response.body, "html.parser")
                for detail_form in soup.select('form[action$="ViewDetailedTestResult"]'):
                    detail = self._post("ViewDetailedTestResult", _fields(detail_form))
                    detail_sequence += 1
                    detail_paths.append(
                        self._save(detail, "test-result-detail", detail_sequence, window=window)
                    )
            captured.append((index_paths, detail_paths))
        return captured

    def write_manifest(self, *, complete: bool) -> None:
        payload = {
            "schema": 1,
            "complete": complete,
            "updated_at": datetime.now(UTC).isoformat(),
            "pages": [asdict(page) for page in self.pages],
        }
        suffix = "json" if complete else "partial.json"
        target = self.destination / f"live-capture-manifest.{suffix}"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(target)
        if complete:
            partial = self.destination / "live-capture-manifest.partial.json"
            partial.unlink(missing_ok=True)
