import pytest

from systmonline_fhir.terminology import (
    ICD_10,
    READ_V2,
    SNOMED_CT,
    Coding,
    MappedConcept,
    MappingStep,
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
