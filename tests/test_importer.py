from pathlib import Path

from systmonline_fhir.fhir import UK_CORE_PACKAGE, bundle
from systmonline_fhir.parser import parse_patient_record


def test_parses_synthetic_record_and_builds_stable_fhir_bundle():
    events = parse_patient_record(Path(__file__).parent / "fixtures" / "synthetic_record.html")
    assert [event.entry_type for event in events] == ["Test result", "Medication"]
    result = bundle(events)
    assert [entry["resource"]["resourceType"] for entry in result["entry"]] == ["Patient", "Observation", "MedicationStatement"]
    assert bundle(events) == result
    assert UK_CORE_PACKAGE == "fhir.r4.ukcore.stu2#2.0.1"
    assert result["entry"][0]["resource"]["meta"]["profile"] == [
        "https://fhir.hl7.org.uk/StructureDefinition/UKCore-Patient"
    ]
    assert result["entry"][1]["resource"]["meta"]["profile"] == [
        "https://fhir.hl7.org.uk/StructureDefinition/UKCore-Observation"
    ]
