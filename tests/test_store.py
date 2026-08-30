from pathlib import Path

from systmonline_fhir.parser import parse_patient_record
from systmonline_fhir.store import RecordStore
from systmonline_fhir.terminology import SNOMED_CT, Coding


def test_retains_raw_source_and_highlights_uncertain_mapping(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "synthetic_record.html"
    content = fixture.read_bytes()
    event = parse_patient_record(fixture)[0]
    store = RecordStore(tmp_path / "records.sqlite3")
    try:
        digest = store.retain_capture(content, "https://example.invalid/patient-record")
        assert digest == event.source_sha256
        event_id = store.add_event(event, "0.1.0")
        assert store.add_event(event, "0.1.0") == event_id
        store.add_coding(
            event_id,
            Coding(SNOMED_CT, "synthetic-proposal", "Synthetic mapping"),
            status="proposed",
            confidence=0.82,
            method="synthetic-test-mapper",
        )
        assert store.counts() == {
            "raw_capture": 1,
            "parsed_event": 1,
            "coding_assertion": 1,
            "analysis_finding": 0,
        }
        queue = store.review_queue()
        assert len(queue) == 1
        assert queue[0]["confidence"] == 0.82
        assert queue[0]["review_required"] == 1
        assert store.event_review_queue() == []
        assert store.events() == [event]
    finally:
        store.close()
