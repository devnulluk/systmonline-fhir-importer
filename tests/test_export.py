import json
from pathlib import Path

from systmonline_fhir.export import export_current
from systmonline_fhir.parser import parse_patient_record
from systmonline_fhir.store import RecordStore


def test_exports_only_current_parser_revision(tmp_path: Path):
    source = Path(__file__).parent / "fixtures" / "synthetic_record.html"
    event = parse_patient_record(source)[0]
    database = tmp_path / "records.sqlite3"
    store = RecordStore(database)
    digest = store.retain_capture(source.read_bytes(), source.resolve().as_uri())
    assert digest == event.source_sha256
    store.add_event(event, "0.2.0", 0.8, ["old parser"])
    store.add_event(event, "0.3.0", 1.0, [])
    store.close()

    canonical = tmp_path / "canonical.json"
    fhir = tmp_path / "bundle.json"
    assert export_current(database, canonical, fhir) == 1
    assert len(json.loads(canonical.read_text(encoding="utf-8"))) == 1
    assert len(json.loads(fhir.read_text(encoding="utf-8"))["entry"]) == 2
