from pathlib import Path

from systmonline_fhir.fhir import bundle
from systmonline_fhir.parser import parse_patient_record


def test_parses_synthetic_record_and_builds_stable_fhir_bundle():
    events = parse_patient_record(Path(__file__).parent / "fixtures" / "synthetic_record.html")
    assert [event.entry_type for event in events] == ["Test result", "Medication"]
    result = bundle(events)
    assert [entry["resource"]["resourceType"] for entry in result["entry"]] == ["Patient", "Observation", "MedicationStatement"]
    assert bundle(events) == result
