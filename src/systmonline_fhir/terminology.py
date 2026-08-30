from __future__ import annotations

from dataclasses import dataclass

READ_V2 = "http://read.info/readv2"
CTV3 = "http://read.info/ctv3"
SNOMED_CT = "http://snomed.info/sct"
ICD_10 = "http://hl7.org/fhir/sid/icd-10"
ICD_11_MMS = "http://id.who.int/icd/release/11/mms"


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
