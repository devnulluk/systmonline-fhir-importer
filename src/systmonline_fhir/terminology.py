from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

READ_V2 = "http://read.info/readv2"
CTV3 = "http://read.info/ctv3"
SNOMED_CT = "http://snomed.info/sct"
ICD_10 = "http://hl7.org/fhir/sid/icd-10"
ICD_11_MMS = "http://id.who.int/icd/release/11/mms"

KNOWN_SYSTEMS = {READ_V2, CTV3, SNOMED_CT, ICD_10, ICD_11_MMS}


@dataclass(frozen=True)
class Coding:
    system: str
    code: str
    display: str | None = None
    version: str | None = None

    def as_fhir(self) -> dict[str, str]:
        return {key: value for key, value in vars(self).items() if value is not None}


@dataclass(frozen=True)
class MappingStep:
    source: Coding
    target: Coding
    map_identifier: str
    map_version: str
    relationship: str
    advice: str | None = None


@dataclass(frozen=True)
class MappedConcept:
    original_text: str
    source: Coding | None
    steps: tuple[MappingStep, ...] = ()

    @property
    def codings(self) -> tuple[Coding, ...]:
        ordered = ([self.source] if self.source else []) + [step.target for step in self.steps]
        seen: set[tuple[str, str, str | None]] = set()
        result: list[Coding] = []
        for coding in ordered:
            key = (coding.system, coding.code, coding.version)
            if key not in seen:
                seen.add(key)
                result.append(coding)
        return tuple(result)

    def as_codeable_concept(self) -> dict:
        return {"coding": [coding.as_fhir() for coding in self.codings], "text": self.original_text}


def validate_mapping_chain(concept: MappedConcept) -> None:
    """Reject untraceable or unsafe terminology conversions."""
    previous = concept.source
    for step in concept.steps:
        if previous is None or step.source != previous:
            raise ValueError("Mapping chain is discontinuous")
        if not step.map_identifier or not step.map_version or not step.relationship:
            raise ValueError("Every mapping step needs an identifier, version and relationship")
        previous = step.target

    systems = [coding.system for coding in concept.codings]
    if ICD_10 in systems and SNOMED_CT not in systems and any(
        system in systems for system in (READ_V2, CTV3)
    ):
        raise ValueError("Historical Read coding must map through SNOMED CT before ICD")


EXPLICIT_CODE_PATTERNS = (
    (READ_V2, re.compile(r"(?i)\bRead\s*(?:v(?:ersion)?\s*)?2\s*code\s*[:=]\s*([A-Za-z0-9.%-]{1,20})")),
    (CTV3, re.compile(r"(?i)\b(?:CTV3|Read\s*(?:v(?:ersion)?\s*)?3)\s*code\s*[:=]\s*([A-Za-z0-9.%-]{1,20})")),
    (SNOMED_CT, re.compile(r"(?i)\bSNOMED(?:\s*CT)?\s*(?:code|SCTID)?\s*[:=]\s*(\d{6,18})\b")),
    (ICD_10, re.compile(r"(?i)\bICD[- ]?10\s*(?:code)?\s*[:=]\s*([A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?)\b")),
)


def extract_explicit_codings(text: str) -> tuple[Coding, ...]:
    """Extract only codes whose coding system is explicitly labelled by the source."""
    codings: list[Coding] = []
    for system, pattern in EXPLICIT_CODE_PATTERNS:
        codings.extend(Coding(system, match.group(1)) for match in pattern.finditer(text))
    return tuple(dict.fromkeys(codings))


class MappingRepository:
    def __init__(self, steps: tuple[MappingStep, ...], *, asset_sha256: str, license_id: str):
        self.steps = steps
        self.asset_sha256 = asset_sha256
        self.license_id = license_id

    def outgoing(self, source: Coding) -> tuple[MappingStep, ...]:
        return tuple(
            step
            for step in self.steps
            if step.source.system == source.system and step.source.code == source.code
        )

    def paths(self, source: Coding, *, max_steps: int = 2) -> tuple[tuple[MappingStep, ...], ...]:
        """Return every versioned mapping path without collapsing ambiguous targets."""
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        found: list[tuple[MappingStep, ...]] = []

        def walk(current: Coding, path: tuple[MappingStep, ...]) -> None:
            candidates = self.outgoing(current)
            if not candidates or len(path) == max_steps:
                if path:
                    concept = MappedConcept(
                        path[0].source.display or path[0].source.code,
                        path[0].source,
                        path,
                    )
                    validate_mapping_chain(concept)
                    found.append(path)
                return
            for step in candidates:
                visited = {(item.source.system, item.source.code) for item in path}
                if (step.target.system, step.target.code) in visited:
                    continue
                walk(step.target, (*path, step))

        walk(source, ())
        return tuple(found)


def load_mapping_csv(
    path: Path,
    *,
    expected_sha256: str,
    license_id: str,
) -> MappingRepository:
    raw = path.read_bytes()
    actual_sha256 = sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("mapping asset checksum does not match its declared SHA-256")
    if not license_id.strip():
        raise ValueError("mapping asset licence identifier is required")
    rows = csv.DictReader(raw.decode("utf-8-sig").splitlines())
    required = {
        "source_system",
        "source_code",
        "target_system",
        "target_code",
        "map_identifier",
        "map_version",
        "relationship",
    }
    if rows.fieldnames is None or not required.issubset(rows.fieldnames):
        raise ValueError("mapping CSV is missing required columns")
    steps: list[MappingStep] = []
    for row_number, row in enumerate(rows, start=2):
        if row["source_system"] not in KNOWN_SYSTEMS or row["target_system"] not in KNOWN_SYSTEMS:
            raise ValueError(f"mapping CSV row {row_number} uses an unknown coding system")
        source = Coding(
            row["source_system"], row["source_code"], row.get("source_display") or None,
            row.get("source_version") or None,
        )
        target = Coding(
            row["target_system"], row["target_code"], row.get("target_display") or None,
            row.get("target_version") or None,
        )
        step = MappingStep(
            source,
            target,
            row["map_identifier"],
            row["map_version"],
            row["relationship"],
            row.get("advice") or None,
        )
        validate_mapping_chain(MappedConcept(row.get("source_display") or source.code, source, (step,)))
        steps.append(step)
    return MappingRepository(tuple(steps), asset_sha256=actual_sha256, license_id=license_id)
