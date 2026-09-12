from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .parser import RecordEvent
from .store import RecordStore
from .terminology import Coding

PARSER_VERSION = "pkb-fhir-r4-v1"
SUPPORTED_RESOURCES = {
    "AllergyIntolerance",
    "Appointment",
    "Condition",
    "DiagnosticReport",
    "DocumentReference",
    "Immunization",
    "MedicationRequest",
    "MedicationStatement",
    "Observation",
    "Procedure",
    "QuestionnaireResponse",
}


@dataclass(frozen=True)
class ImportResult:
    resources_seen: int
    events_added: int
    resources_skipped: int


def _first_text(concept: Any) -> str | None:
    if not isinstance(concept, dict):
        return None
    if text := concept.get("text"):
        return str(text)
    for coding in concept.get("coding", []):
        if isinstance(coding, dict) and coding.get("display"):
            return str(coding["display"])
    return None


def _date(resource: dict[str, Any]) -> str:
    for key in (
        "effectiveDateTime",
        "effectiveInstant",
        "issued",
        "onsetDateTime",
        "authoredOn",
        "recordedDate",
        "occurrenceDateTime",
        "date",
        "created",
        "start",
    ):
        value = resource.get(key)
        if isinstance(value, str) and value:
            return value[:10]
    period = resource.get("effectivePeriod") or resource.get("period")
    if isinstance(period, dict) and isinstance(period.get("start"), str):
        return period["start"][:10]
    return "unknown"


def _summary(resource: dict[str, Any]) -> str:
    label = None
    for key in ("code", "medicationCodeableConcept", "vaccineCode", "type", "reasonCode"):
        value = resource.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if text := _first_text(value):
            label = text
            break
    label = label or str(resource.get("description") or resource["resourceType"])
    value = resource.get("valueQuantity")
    if isinstance(value, dict) and value.get("value") is not None:
        unit = value.get("unit") or value.get("code") or ""
        return f"{label}: {value['value']} {unit}".strip()
    if text := _first_text(resource.get("valueCodeableConcept")):
        return f"{label}: {text}"
    if resource.get("valueString") is not None:
        return f"{label}: {resource['valueString']}"
    if resource.get("valueBoolean") is not None:
        return f"{label}: {resource['valueBoolean']}"
    return f"{label} ({resource['status']})" if resource.get("status") else label


def _codings(value: Any) -> Iterable[Coding]:
    if isinstance(value, list):
        for item in value:
            yield from _codings(item)
        return
    if not isinstance(value, dict):
        return
    for coding in value.get("coding", []):
        if not isinstance(coding, dict) or not coding.get("system") or not coding.get("code"):
            continue
        yield Coding(
            str(coding["system"]),
            str(coding["code"]),
            str(coding["display"]) if coding.get("display") else None,
            str(coding["version"]) if coding.get("version") else None,
        )


def _resource_codings(resource: dict[str, Any]) -> Iterable[Coding]:
    seen: set[tuple[str, str, str | None]] = set()
    # Keep this list explicit.  These are the CodeableConcept fields that
    # commonly carry clinically meaningful source assertions in the supported
    # resource set.  Do not recursively walk arbitrary JSON: that could turn
    # administrative or narrative extensions into false clinical codings.
    for key in (
        "code",
        "category",
        "medicationCodeableConcept",
        "vaccineCode",
        "type",
        "reasonCode",
        "reasonReference",
        "serviceType",
        "verificationStatus",
        "conclusionCode",
    ):
        for coding in _codings(resource.get(key)):
            identity = (coding.system, coding.code, coding.version)
            if identity not in seen:
                seen.add(identity)
                yield coding


def import_bundle(
    path: Path, store: RecordStore, source_uri: str = "pkb-fhir-export"
) -> ImportResult:
    raw = path.read_bytes()
    bundle = json.loads(raw)
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("Patients Know Best import must be a FHIR Bundle")
    digest = store.retain_capture(raw, source_uri, "application/fhir+json")
    entries = bundle.get("entry", [])
    if not isinstance(entries, list):
        raise TypeError("FHIR Bundle entry must be an array")

    added = 0
    skipped = 0
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if (
            not isinstance(resource, dict)
            or resource.get("resourceType") not in SUPPORTED_RESOURCES
        ):
            skipped += 1
            continue
        resource_type = str(resource["resourceType"])
        resource_id = str(resource.get("id") or f"entry-{added + skipped}")
        event = RecordEvent(
            date=_date(resource),
            author="Supplied as FHIR by Patients Know Best",
            organisation="Patients Know Best",
            entry_type=resource_type,
            text=_summary(resource),
            source_file=f"pkb-fhir:{resource_type}/{resource_id}",
            source_sha256=digest,
        )
        notes = [] if event.date != "unknown" else ["FHIR resource has no supported event date"]
        event_id = store.add_event(
            event,
            PARSER_VERSION,
            confidence=1.0 if not notes else 0.9,
            notes=notes,
        )
        for coding in _resource_codings(resource):
            store.add_coding(
                event_id,
                coding,
                status="source",
                confidence=1.0,
                method="pkb-fhir-source-coding",
            )
        added += 1
    return ImportResult(len(entries), added, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preserve and import a Patients Know Best FHIR R4 Bundle"
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source-uri", default="pkb-fhir-export")
    args = parser.parse_args()
    store = RecordStore(args.database)
    try:
        result = import_bundle(args.bundle, store, args.source_uri)
    finally:
        store.close()
    print(
        f"Preserved {result.resources_seen} resources; imported {result.events_added}; "
        f"skipped {result.resources_skipped}."
    )


if __name__ == "__main__":
    main()
