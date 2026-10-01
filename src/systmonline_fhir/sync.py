from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from .credentials import _read_setting, load_credentials
from .live import RequestsTransport, SystmOnlineClient
from .pipeline import ingest_supported_views, ingest_test_result_details
from .store import RecordStore


def _date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=UTC).date()


def _upload(database: Path, url: str, token: str) -> None:
    boundary = "----systmonline-fhir-import"
    content = database.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"database\"; "
        f"filename=\"{database.name}\"\r\nContent-Type: "
        f"{mimetypes.guess_type(database.name)[0] or 'application/octet-stream'}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Import-Token": token,
        },
    )
    with urlopen(request, timeout=120) as response:
        if response.status not in {200, 201, 204}:
            raise RuntimeError(f"portal import returned HTTP {response.status}")


def run_once(environment: dict[str, str] | None = None) -> dict[str, object]:
    env = dict(os.environ if environment is None else environment)
    root = Path(env.get("SYSTMONLINE_DATA_DIR", "/data"))
    database = Path(env.get("SYSTMONLINE_DATABASE", str(root / "records.sqlite3")))
    capture = root / "captures" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    status_path = root / "status.json"
    database.parent.mkdir(parents=True, exist_ok=True)
    configured_start = _date(env.get("SYSTMONLINE_HISTORY_START", "01/01/1900"))
    end = _date(
        env.get("SYSTMONLINE_HISTORY_END", datetime.now(UTC).date().strftime("%d/%m/%Y"))
    )
    previous: dict[str, object] = {}
    if status_path.exists():
        try:
            previous = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    full_backfill = not bool(previous.get("history_complete"))
    lookback_days = int(env.get("SYSTMONLINE_REFRESH_LOOKBACK_DAYS", "120"))
    start = (
        configured_start
        if full_backfill
        else max(configured_start, end - timedelta(days=lookback_days))
    )
    client = SystmOnlineClient(
        env.get("SYSTMONLINE_BASE_URL", "https://systmonline.tpp-uk.com/2/"),
        RequestsTransport(timeout=float(env.get("SYSTMONLINE_TIMEOUT_SECONDS", "60"))),
        capture,
        delay_seconds=float(env.get("SYSTMONLINE_DELAY_SECONDS", "1")),
    )
    status: dict[str, object] = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "history_complete": not full_backfill,
    }
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    try:
        menu = client.login(load_credentials(env))
        patient_pages = client.capture_patient_record(menu, start, end)
        windows = client.capture_test_results(
            menu, start, end, window_days=int(env.get("SYSTMONLINE_WINDOW_DAYS", "60"))
        )
        store = RecordStore(database)
        try:
            ingest_supported_views(patient_pages, store, report_path=capture / "patient-reconciliation.json")
            result_events = 0
            for sequence, (index_pages, detail_pages) in enumerate(windows, start=1):
                if not detail_pages:
                    continue
                result_events += len(
                    ingest_test_result_details(
                        index_pages,
                        detail_pages,
                        store,
                        report_path=capture / f"test-result-reconciliation-{sequence:04d}.json",
                    )
                )
            counts = store.counts()
        finally:
            store.close()
        client.write_manifest(complete=True)
        portal_url = env.get("CLINICAL_IMPORT_URL", "").strip()
        if portal_url:
            _upload(database, portal_url, _read_setting("CLINICAL_IMPORT_TOKEN", env))
        status = {
            "status": "complete",
            "completed_at": datetime.now(UTC).isoformat(),
            "history_start": start.isoformat(),
            "history_end": end.isoformat(),
            "history_complete": True,
            "capture_mode": "historical-backfill" if full_backfill else "incremental-refresh",
            "patient_record_pages": len(patient_pages),
            "test_result_windows": len(windows),
            "test_result_events": result_events,
            "database_counts": counts,
            "portal_uploaded": bool(portal_url),
        }
    except Exception as error:
        status = {
            "status": "failed",
            "failed_at": datetime.now(UTC).isoformat(),
            "history_complete": not full_backfill,
            "error_type": type(error).__name__,
            "message": str(error),
        }
        raise
    finally:
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture and reconcile an authorised SystmOnline record")
    parser.add_argument("--loop", action="store_true", help="repeat using SYSTMONLINE_SYNC_INTERVAL_HOURS")
    args = parser.parse_args()
    while True:
        print(json.dumps(run_once(), indent=2))
        if not args.loop:
            return
        time.sleep(float(os.environ.get("SYSTMONLINE_SYNC_INTERVAL_HOURS", "24")) * 3600)


if __name__ == "__main__":
    main()
