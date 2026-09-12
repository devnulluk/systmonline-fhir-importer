import json

import pytest

from systmonline_fhir.pkb import import_bundle
from systmonline_fhir.store import RecordStore


def test_imports_and_preserves_pkb_fhir_bundle(tmp_path):
    source = tmp_path / "pkb.json"
    source.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": "synthetic-observation",
                            "status": "final",
                            "effectiveDateTime": "2026-01-02T10:00:00Z",
                            "valueQuantity": {"value": 42, "unit": "synthetic units"},
                            "code": {
                                "coding": [
                                    {
                                        "system": "http://snomed.info/sct",
                                        "code": "synthetic-code",
                                        "display": "Synthetic observation",
                                    }
                                ]
                            },
                        }
                    },
                    {"resource": {"resourceType": "Patient", "id": "synthetic-patient"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    database = tmp_path / "records.sqlite3"
    store = RecordStore(database)
    try:
        result = import_bundle(source, store, "https://example.invalid/pkb/fhir")
        assert result.resources_seen == 2
        assert result.events_added == 1
        assert result.resources_skipped == 1
        assert store.counts() == {
            "raw_capture": 1,
            "parsed_event": 1,
            "coding_assertion": 1,
            "coding_review": 0,
            "analysis_finding": 0,
        }
        event = store.events()[0]
        assert event.date == "2026-01-02"
        assert event.entry_type == "Observation"
        assert event.text == "Synthetic observation: 42 synthetic units"
        assert event.source_file == "pkb-fhir:Observation/synthetic-observation"
        capture = store.connection.execute("SELECT content FROM raw_capture").fetchone()[0]
        assert capture == source.read_bytes()
        coding = store.connection.execute("SELECT * FROM coding_assertion").fetchone()
        assert coding["system"] == "http://snomed.info/sct"
        assert coding["status"] == "source"
        assert coding["confidence"] == 1.0
    finally:
        store.close()


def test_rejects_non_bundle_json(tmp_path):
    source = tmp_path / "not-a-bundle.json"
    source.write_text('{"resourceType":"Observation"}', encoding="utf-8")
    store = RecordStore(tmp_path / "records.sqlite3")
    try:
        with pytest.raises(ValueError, match="FHIR Bundle"):
            import_bundle(source, store)
    finally:
        store.close()


def test_rejects_bundle_with_non_array_entries(tmp_path):
    source = tmp_path / "invalid-entries.json"
    source.write_text(
        '{"resourceType":"Bundle","entry":{"resourceType":"Observation"}}',
        encoding="utf-8",
    )
    store = RecordStore(tmp_path / "records.sqlite3")
    try:
        with pytest.raises(TypeError, match="entry must be an array"):
            import_bundle(source, store)
    finally:
        store.close()


def test_captures_supported_codeable_concept_fields_without_recursive_inference(tmp_path):
    source = tmp_path / "pkb.json"
    source.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Appointment",
                            "id": "appointment-1",
                            "status": "booked",
                            "reasonCode": {
                                "coding": [
                                    {
                                        "system": "http://snomed.info/sct",
                                        "code": "123",
                                        "display": "Source reason",
                                    }
                                ]
                            },
                            "extension": [
                                {
                                    "url": "https://example.invalid/extension",
                                    "valueCodeableConcept": {
                                        "coding": [
                                            {
                                                "system": "http://snomed.info/sct",
                                                "code": "999",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store = RecordStore(tmp_path / "records.sqlite3")
    try:
        result = import_bundle(source, store)
        assert result.events_added == 1
        codings = store.connection.execute(
            "SELECT system, code, display FROM coding_assertion ORDER BY code"
        ).fetchall()
        assert [(row["system"], row["code"], row["display"]) for row in codings] == [
            ("http://snomed.info/sct", "123", "Source reason")
        ]
    finally:
        store.close()
