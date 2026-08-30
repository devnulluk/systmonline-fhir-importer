from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from .fhir import bundle
from .parser import RecordEvent, parse_patient_record, parse_supported_view
from .store import RecordStore

PARSER_VERSION = "0.3.0"


@dataclass(frozen=True)
class ReconciliationItem:
    filename: str
    sha256: str
    source_kind: str
    parsed_events: int
    unique_events: int
    duplicate_events: int
    unknown_dates: int
    review_items: int
    status: str


def ingest_supported_views(
    pages: list[Path], store: RecordStore, *, report_path: Path | None = None
) -> list[RecordEvent]:
    events: list[RecordEvent] = []
    report: list[ReconciliationItem] = []
    for page in pages:
        raw = page.read_bytes()
        digest = store.retain_capture(raw, page.resolve().as_uri(), "text/html; capture=rendered-dom")
        source_kind, parsed = parse_supported_view(page)
        if any(event.source_sha256 != digest for event in parsed):
            raise RuntimeError(f"parser checksum mismatch for {page}")
        for event in parsed:
            notes: list[str] = []
            confidence = 1.0
            if event.date == "unknown":
                confidence = 0.9
                notes.append("Source view did not provide a parseable event date")
            if event.entry_type == "Test result index":
                notes.append("Index entry only; result detail has not yet been captured")
            store.add_event(event, PARSER_VERSION, confidence, notes)
        status = "unsupported" if source_kind == "unsupported" else "parsed"
        unique = list(dict.fromkeys(parsed))
        duplicate_events = len(parsed) - len(unique)
        unknown_dates = sum(event.date == "unknown" for event in parsed)
        review_items = (
            sum(event.date == "unknown" or event.entry_type == "Test result index" for event in parsed)
            + duplicate_events
        )
        report.append(
            ReconciliationItem(
                page.name,
                sha256(raw).hexdigest(),
                source_kind,
                len(parsed),
                len(unique),
                duplicate_events,
                unknown_dates,
                review_items,
                status,
            )
        )
        events.extend(unique)
    if report_path:
        report_path.write_text(json.dumps([asdict(item) for item in report], indent=2), encoding="utf-8")
    return list(dict.fromkeys(events))


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
