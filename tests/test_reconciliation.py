import json
from pathlib import Path

from systmonline_fhir.pipeline import ingest_supported_views
from systmonline_fhir.store import RecordStore


def test_reconciles_mixed_views_and_is_idempotent(tmp_path: Path):
    fixtures = Path(__file__).parent / "fixtures"
    pages = [
        fixtures / "synthetic_record.html",
        fixtures / "synthetic_summary.html",
        fixtures / "synthetic_test_results.html",
        fixtures / "synthetic_vaccinations.html",
    ]
    store = RecordStore(tmp_path / "records.sqlite3")
    report = tmp_path / "reconciliation.json"

    first = ingest_supported_views(pages, store, report_path=report)
    second = ingest_supported_views(pages, store, report_path=report)

    assert len(first) == len(second) == 8
    assert store.counts()["raw_capture"] == 4
    assert store.counts()["parsed_event"] == 8
    rows = json.loads(report.read_text(encoding="utf-8"))
    assert {row["source_kind"] for row in rows} == {
        "patient_record",
        "summary_patient_record",
        "test_results_index",
        "childhood_vaccinations",
    }
    assert all(row["status"] == "parsed" for row in rows)
    assert all(row["duplicate_events"] == 0 for row in rows)
    assert sum(row["review_items"] for row in rows) == 1
    assert len(store.event_review_queue()) == 1
    store.close()
