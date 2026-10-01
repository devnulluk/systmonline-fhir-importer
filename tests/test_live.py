from datetime import date
from pathlib import Path

from systmonline_fhir.capture import Response
from systmonline_fhir.credentials import Credentials
from systmonline_fhir.live import SystmOnlineClient, historical_windows


def page(url: str, body: str) -> Response:
    return Response(url, 200, "text/html", body.encode())


class ScriptedTransport:
    def __init__(self, responses: list[Response]):
        self.responses = iter(responses)
        self.posts: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str) -> Response:
        return next(self.responses)

    def post(self, url: str, data: dict[str, str]) -> Response:
        self.posts.append((url, data))
        return next(self.responses)


def test_historical_windows_are_complete_newest_first():
    assert historical_windows(date(2026, 1, 1), date(2026, 3, 5), 60) == [
        (date(2026, 1, 5), date(2026, 3, 5)),
        (date(2026, 1, 1), date(2026, 1, 4)),
    ]


def test_login_posts_credentials_without_putting_them_in_manifest(tmp_path: Path):
    login = page(
        "https://example.test/2/Login",
        '<form action="Login"><input name="UUID" value="session">'
        '<input name="Username"><input name="Password" type="password"></form>',
    )
    menu = page("https://example.test/2/MainMenu", "<h1>Main menu</h1>")
    transport = ScriptedTransport([login, login, menu])
    client = SystmOnlineClient("https://example.test/2/", transport, tmp_path, delay_seconds=0)

    assert client.login(Credentials("person", "secret")) == menu
    assert transport.posts[0][1]["Username"] == "person"
    client.write_manifest(complete=True)
    manifest = (tmp_path / "live-capture-manifest.json").read_text()
    assert "person" not in manifest
    assert "secret" not in manifest
    assert "session" not in manifest


def test_patient_record_uses_post_pagination_and_full_range(tmp_path: Path):
    menu = page(
        "https://example.test/2/MainMenu",
        '<form action="PatientRecord"><input name="UUID" value="s">'
        '<input name="Patient Record"></form>',
    )
    landing = page(
        "https://example.test/2/PatientRecord",
        '<form action="PatientRecord"><input name="UUID" value="s">'
        '<input name="DateFrom"><input name="DateTo"><input name="TextSearch">'
        '<input name="Search"><input name="IncludeUnknownDates" type="checkbox"></form>',
    )
    first = page("https://example.test/2/PatientRecord", "<h2>Patient Record (Page 1/2)</h2>")
    second = page("https://example.test/2/PatientRecord", "<h2>Patient Record (Page 2/2)</h2>")
    transport = ScriptedTransport([landing, first, second])
    client = SystmOnlineClient("https://example.test/2/", transport, tmp_path, delay_seconds=0)

    paths = client.capture_patient_record(menu, date(1900, 1, 1), date(2026, 10, 1))

    assert len(paths) == 2
    assert transport.posts[1][1]["DateFrom"] == "01/01/1900"
    assert transport.posts[1][1]["IncludeUnknownDates"] == "on"
    assert transport.posts[2][1]["Page2"] == "Page2"


def test_test_results_captures_each_detail_in_index_order(tmp_path: Path):
    menu = page(
        "https://example.test/2/MainMenu",
        '<form action="ViewTestResults"><input name="UUID" value="s">'
        '<input name="View Test Results"></form>',
    )
    landing = page(
        "https://example.test/2/ViewTestResults",
        '<form action="ViewTestResults"><input name="UUID" value="s">'
        '<input name="ResultsFrom"><input name="ResultsTo"><input name="Search"></form>',
    )
    index = page(
        "https://example.test/2/ViewTestResults",
        '<h2>Test Results (Page 1/1)</h2>'
        '<form action="ViewDetailedTestResult"><input name="UUID" value="s">'
        '<input name="TestResultId" value="opaque"></form>',
    )
    detail = page("https://example.test/2/ViewDetailedTestResult", "<h2>View Test Result</h2>")
    transport = ScriptedTransport([landing, index, detail])
    client = SystmOnlineClient("https://example.test/2/", transport, tmp_path, delay_seconds=0)

    windows = client.capture_test_results(menu, date(2026, 8, 1), date(2026, 8, 30))

    assert len(windows) == 1
    assert len(windows[0][0]) == len(windows[0][1]) == 1
    assert transport.posts[-1][1]["TestResultId"] == "opaque"
    manifest = (tmp_path / "live-capture-manifest.partial.json").read_text()
    assert "opaque" not in manifest
    assert "UUID" not in manifest
