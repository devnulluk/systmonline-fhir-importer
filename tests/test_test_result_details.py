import json
from pathlib import Path

from systmonline_fhir.parser import parse_pathology_observations
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

    assert len(events) == 3
    assert events[0].entry_type == "Test result"
    assert events[0].date == "2026-04-05"
    queue = store.event_review_queue()
    assert len(queue) == 3
    assert all(item["parse_confidence"] == 0.99 for item in queue)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report[0]["review_required"] is True
    assert report[0]["laboratory_observations"] == 2
    store.close()


def test_extracts_numeric_pathology_rows_and_reference_interval():
    observations = parse_pathology_observations(FIXTURES / "synthetic_test_result_detail.html")
    assert len(observations) == 2
    assert observations[0].name == "Serum example level"
    assert observations[0].value == 42.5
    assert observations[0].unit == "mmol/L"
    assert observations[0].reference_low == 10
    assert observations[0].reference_high == 50
    assert observations[0].narrative == "Example source comment"
