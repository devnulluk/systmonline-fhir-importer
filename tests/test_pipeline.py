from pathlib import Path

from systmonline_fhir.pipeline import ingest_saved_pages
from systmonline_fhir.store import RecordStore


def test_pipeline_retains_source_before_persisting_events(tmp_path: Path):
    source = Path(__file__).parent / "fixtures" / "synthetic_record.html"
    store = RecordStore(tmp_path / "records.sqlite3")

    events = ingest_saved_pages(
        [source],
        store,
        canonical_path=tmp_path / "canonical.json",
        fhir_path=tmp_path / "bundle.json",
    )

    assert len(events) == 2
    assert store.counts()["raw_capture"] == 1
    assert store.counts()["parsed_event"] == 2
    assert (tmp_path / "canonical.json").exists()
    assert (tmp_path / "bundle.json").exists()
    store.close()
