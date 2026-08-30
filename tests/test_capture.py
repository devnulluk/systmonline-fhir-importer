from pathlib import Path

import pytest

from systmonline_fhir.capture import CaptureError, Response, SessionExpired, capture_pages
from systmonline_fhir.store import RecordStore


class FakeTransport:
    def __init__(self, responses: dict[str, Response]):
        self.responses = responses
        self.requested: list[str] = []

    def get(self, url: str) -> Response:
        self.requested.append(url)
        return self.responses[url]


def response(url: str, body: str) -> Response:
    return Response(url, 200, "text/html; charset=utf-8", body.encode())


def test_retains_every_page_before_following_pagination(tmp_path: Path):
    first = "https://example.test/record?page=1"
    second = "https://example.test/record?page=2"
    transport = FakeTransport(
        {
            first: response(first, '<table></table><a rel="next" href="?page=2">Next</a>'),
            second: response(second, "<table></table>"),
        }
    )
    store = RecordStore(tmp_path / "records.sqlite3")

    manifest = capture_pages(
        first,
        tmp_path / "raw",
        transport,
        retain=store.retain_capture,
        delay_seconds=0,
    )

    assert transport.requested == [first, second]
    assert len(manifest.pages) == 2
    assert store.counts()["raw_capture"] == 2
    assert (tmp_path / "raw" / "capture-manifest.json").exists()
    assert not (tmp_path / "raw" / "capture-manifest.partial.json").exists()
    store.close()


def test_stops_on_login_page_but_preserves_it(tmp_path: Path):
    url = "https://example.test/2/Login"
    transport = FakeTransport(
        {url: response(url, '<form><input type="password"><button>Sign in</button></form>')}
    )
    store = RecordStore(tmp_path / "records.sqlite3")

    with pytest.raises(SessionExpired):
        capture_pages(url, tmp_path / "raw", transport, retain=store.retain_capture)

    assert store.counts()["raw_capture"] == 1
    assert (tmp_path / "raw" / "capture-manifest.partial.json").exists()
    store.close()


def test_detects_pagination_loop(tmp_path: Path):
    url = "https://example.test/record"
    transport = FakeTransport(
        {url: response(url, '<a rel="next" href="/record">Next</a>')}
    )

    with pytest.raises(CaptureError, match="pagination loop"):
        capture_pages(url, tmp_path / "raw", transport, delay_seconds=0)
