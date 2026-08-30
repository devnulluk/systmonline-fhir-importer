from hashlib import sha256
from pathlib import Path

import pytest

from systmonline_fhir.terminology import (
    ICD_10,
    READ_V2,
    SNOMED_CT,
    Coding,
    MappedConcept,
    MappingStep,
    extract_explicit_codings,
    load_mapping_csv,
    validate_mapping_chain,
)


def test_preserves_read_snomed_and_icd_with_mapping_provenance():
    read = Coding(READ_V2, "synthetic-read")
    snomed = Coding(SNOMED_CT, "synthetic-snomed")
    icd = Coding(ICD_10, "SYNTHETIC")
    concept = MappedConcept(
        "Synthetic condition",
        read,
        (
            MappingStep(read, snomed, "nhs-read-to-snomed", "synthetic-version", "equivalent"),
            MappingStep(snomed, icd, "nhs-snomed-to-icd10", "synthetic-version", "related-to"),
        ),
    )
    validate_mapping_chain(concept)
    assert [item["system"] for item in concept.as_codeable_concept()["coding"]] == [
        READ_V2,
        SNOMED_CT,
        ICD_10,
    ]


def test_rejects_untraceable_read_to_icd_shortcut():
    read = Coding(READ_V2, "synthetic-read")
    icd = Coding(ICD_10, "SYNTHETIC")
    concept = MappedConcept(
        "Synthetic condition",
        read,
        (MappingStep(read, icd, "unapproved-map", "1", "related-to"),),
    )
    with pytest.raises(ValueError, match="through SNOMED"):
        validate_mapping_chain(concept)


def test_extracts_only_explicitly_labelled_codes():
    codings = extract_explicit_codings(
        "Description R1234; Read v2 code: R1234; SNOMED CT code: 123456789"
    )
    assert [(coding.system, coding.code) for coding in codings] == [
        (READ_V2, "R1234"),
        (SNOMED_CT, "123456789"),
    ]
    assert extract_explicit_codings("Unlabelled R1234 and 123456789") == ()


def test_loads_only_checksummed_licensed_mapping_assets():
    fixture = Path(__file__).parent / "fixtures" / "synthetic_mapping.csv"
    digest = sha256(fixture.read_bytes()).hexdigest()
    repository = load_mapping_csv(
        fixture, expected_sha256=digest, license_id="synthetic-test-only"
    )
    outgoing = repository.outgoing(Coding(READ_V2, "R1234"))
    assert len(outgoing) == 1
    assert outgoing[0].target == Coding(SNOMED_CT, "123456789", "Synthetic target", "20260701")
    paths = repository.paths(Coding(READ_V2, "R1234"))
    assert len(paths) == 1
    assert [step.target.system for step in paths[0]] == [SNOMED_CT, ICD_10]
    with pytest.raises(ValueError, match="checksum"):
        load_mapping_csv(fixture, expected_sha256="0" * 64, license_id="synthetic")
