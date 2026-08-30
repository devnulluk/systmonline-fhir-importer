import json
from pathlib import Path

from systmonline_fhir.pipeline import ingest_test_result_details
from systmonline_fhir.store import RecordStore

FIXTURES = Path(__file__).parent / "fixtures"


def test_links_detail_to_index_with_explicit_non_absolute_confidence(tmp_path: Path):
    store = RecordStore(tmp_path / "records.sqlite3")
    report_path = tmp_path / "detail-reconciliation.json"

    events = ingest_test_result_details(
        [FIXTURES / "synthetic_test_results.html"],
        [FIXTURES / "synthetic_test_result_detail.html"],
        store,
        report_path=report_path,
    )

    assert len(events) == 1
    assert events[0].entry_type == "Test result"
    assert events[0].date == "2026-04-05"
    queue = store.event_review_queue()
    assert len(queue) == 1
    assert queue[0]["parse_confidence"] == 0.99
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report[0]["review_required"] is True
    store.close()
