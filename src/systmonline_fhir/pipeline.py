from __future__ import annotations

import json
from pathlib import Path

from .fhir import bundle
from .parser import RecordEvent, parse_patient_record
from .store import RecordStore

PARSER_VERSION = "0.1.0"


def ingest_saved_pages(
    pages: list[Path],
    store: RecordStore,
    *,
    canonical_path: Path | None = None,
    fhir_path: Path | None = None,
) -> list[RecordEvent]:
    """Retain source pages, parse them, and persist traceable events in that order."""
    events: list[RecordEvent] = []
    for page in pages:
        raw = page.read_bytes()
        digest = store.retain_capture(raw, page.resolve().as_uri(), "text/html")
        parsed = parse_patient_record(page)
        for event in parsed:
            if event.source_sha256 != digest:
                raise RuntimeError(f"parser checksum mismatch for {page}")
            store.add_event(event, PARSER_VERSION)
        events.extend(parsed)

    if canonical_path:
        canonical_path.write_text(
            json.dumps([event.as_dict() for event in events], indent=2), encoding="utf-8"
        )
    if fhir_path:
        fhir_path.write_text(json.dumps(bundle(events), indent=2), encoding="utf-8")
    return events
