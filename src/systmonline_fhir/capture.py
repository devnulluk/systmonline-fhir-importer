from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

from bs4 import BeautifulSoup


class CaptureError(RuntimeError):
    """Raised when a capture cannot safely continue."""


class SessionExpired(CaptureError):
    """Raised when SystmOnline returns a login page during capture."""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    content_type: str
    body: bytes


class Transport(Protocol):
    def get(self, url: str) -> Response: ...


@dataclass(frozen=True)
class CapturedPage:
    sequence: int
    url: str
    status: int
    content_type: str
    sha256: str
    byte_count: int
    captured_at: str
    filename: str


@dataclass(frozen=True)
class CaptureManifest:
    started_at: str
    completed_at: str
    start_url: str
    pages: tuple[CapturedPage, ...]

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def _is_login_page(response: Response) -> bool:
    final_path = response.url.lower().rstrip("/")
    if final_path.endswith(("/login", "/2/login")):
        return True
    soup = BeautifulSoup(response.body, "html.parser")
    has_password = soup.select_one('input[type="password"]') is not None
    text = " ".join(soup.get_text(" ", strip=True).lower().split())
    return has_password and ("sign in" in text or "log in" in text or "login" in text)


def _next_url(response: Response) -> str | None:
    soup = BeautifulSoup(response.body, "html.parser")
    selectors = (
        'a[rel="next"]',
        'a[aria-label*="next" i]',
        'a[title*="next" i]',
        '.pagination a.next',
    )
    for selector in selectors:
        link = soup.select_one(selector)
        if link and link.get("href"):
            return urljoin(response.url, str(link["href"]))
    for link in soup.select("a[href]"):
        label = " ".join(link.get_text(" ", strip=True).lower().split())
        if label in {"next", "next page", ">", "›", "»"}:
            return urljoin(response.url, str(link["href"]))
    return None


def capture_pages(
    start_url: str,
    destination: Path,
    transport: Transport,
    *,
    retain: Callable[[bytes, str, str], str] | None = None,
    delay_seconds: float = 1.0,
    max_pages: int = 1000,
    sleep: Callable[[float], None] = time.sleep,
) -> CaptureManifest:
    """Capture a paginated record, retaining each response before inspecting it."""
    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")

    destination.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(UTC).isoformat()
    pages: list[CapturedPage] = []
    visited: set[str] = set()
    url: str | None = start_url

    while url:
        if url in visited:
            raise CaptureError(f"pagination loop detected at {url}")
        if len(pages) >= max_pages:
            raise CaptureError(f"capture exceeded the {max_pages}-page safety limit")
        visited.add(url)

        response = transport.get(url)
        if response.status != 200:
            raise CaptureError(f"HTTP {response.status} while capturing {url}")

        digest = sha256(response.body).hexdigest()
        sequence = len(pages) + 1
        filename = f"page-{sequence:04d}-{digest[:12]}.html"
        (destination / filename).write_bytes(response.body)
        if retain is not None:
            retained_digest = retain(response.body, response.url, response.content_type)
            if retained_digest != digest:
                raise CaptureError("retained source checksum does not match captured response")

        captured = CapturedPage(
            sequence=sequence,
            url=response.url,
            status=response.status,
            content_type=response.content_type,
            sha256=digest,
            byte_count=len(response.body),
            captured_at=datetime.now(UTC).isoformat(),
            filename=filename,
        )
        pages.append(captured)
        CaptureManifest(started_at, "", start_url, tuple(pages)).write(
            destination / "capture-manifest.partial.json"
        )

        if _is_login_page(response):
            raise SessionExpired(
                "SystmOnline session expired; the returned login page was retained but not parsed"
            )
        url = _next_url(response)
        if url:
            sleep(delay_seconds)

    manifest = CaptureManifest(
        started_at=started_at,
        completed_at=datetime.now(UTC).isoformat(),
        start_url=start_url,
        pages=tuple(pages),
    )
    manifest.write(destination / "capture-manifest.json")
    partial = destination / "capture-manifest.partial.json"
    if partial.exists():
        partial.unlink()
    return manifest
