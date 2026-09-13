from pathlib import Path

from systmonline_fhir.fhir import bundle
from systmonline_fhir.parser import (
    parse_childhood_vaccinations,
    parse_patient_record_observations,
    parse_summary_record,
    parse_test_results_index,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_summary_sections_without_inventing_provenance():
    events = parse_summary_record(FIXTURES / "synthetic_summary.html")
    assert [event.entry_type for event in events] == [
        "Drug sensitivity",
        "Medication",
        "Medication",
    ]
    assert events[0].date == "2020-01-02"
    assert events[0].author == "Not supplied by source view"


def test_parses_test_result_index():
    events = parse_test_results_index(FIXTURES / "synthetic_test_results.html")
    assert len(events) == 1
    assert events[0].date == "2026-04-05"
    assert events[0].entry_type == "Test result index"
    assert events[0].text == "Example panel — Filed result"
    assert bundle(events)["entry"][1]["resource"]["resourceType"] == "Basic"


def test_parses_vaccination_grid_and_supports_unknown_dates_in_fhir():
    events = parse_childhood_vaccinations(FIXTURES / "synthetic_vaccinations.html")
    assert len(events) == 1
    assert events[0].date == "2020-05-06"
    immunization = bundle(events)["entry"][1]["resource"]
    assert immunization["occurrenceDateTime"] == "2020-05-06"


def test_recovers_numeric_laboratory_line_from_patient_record(tmp_path: Path):
    page = tmp_path / "record.html"
    page.write_text("""<main><table>
      <tr><td>01 Jan 2024</td><td>Example clinician</td><td>Example practice</td></tr>
      <tr><td>Coded entry</td><td>Administrative number: 12345<br>Haemoglobin A1c level 41 mmol/mol</td></tr>
    </table></main>""", encoding="utf-8")
    events = parse_patient_record_observations(page)
    assert len(events) == 1
    assert events[0].entry_type == "Laboratory observation"
    assert "Value: 41" in events[0].text
    assert "Unit: mmol/mol" in events[0].text
