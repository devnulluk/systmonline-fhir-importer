from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from .fhir import bundle
from .parser import (
    RecordEvent,
    link_test_result_detail,
    parse_patient_record,
    parse_supported_view,
    parse_test_result_detail,
    parse_test_results_index,
)
from .store import RecordStore

PARSER_VERSION = "0.4.0"


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


def ingest_test_result_details(
    index_pages: list[Path],
    detail_pages: list[Path],
    store: RecordStore,
    *,
    report_path: Path | None = None,
) -> list[RecordEvent]:
    index_events = [event for page in index_pages for event in parse_test_results_index(page)]
    details = [parse_test_result_detail(page) for page in detail_pages]
    if any(detail is None for detail in details):
        raise RuntimeError("one or more result detail pages has an unsupported structure")
    if len(index_events) != len(details):
        raise RuntimeError(
            f"result reconciliation failed: {len(index_events)} index entries and {len(details)} details"
        )

    events: list[RecordEvent] = []
    report: list[dict] = []
    for sequence, (index_event, detail) in enumerate(zip(index_events, details, strict=True), start=1):
        assert detail is not None
        detail_path = detail_pages[sequence - 1]
        retained = store.retain_capture(
            detail_path.read_bytes(), detail_path.resolve().as_uri(), "text/html; capture=rendered-dom"
        )
        if retained != detail.source_sha256:
            raise RuntimeError(f"detail checksum mismatch for {detail_path}")
        event, confidence, notes = link_test_result_detail(index_event, detail)
        store.add_event(event, PARSER_VERSION, confidence, notes)
        events.append(event)
        report.append(
            {
                "sequence": sequence,
                "index_source_sha256": index_event.source_sha256,
                "detail_source_sha256": detail.source_sha256,
                "confidence": confidence,
                "review_required": confidence < 1,
                "notes": notes,
            }
        )
    if report_path:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return events


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
