# Terminology and classification

## Purpose

The importer preserves clinical meaning and also supplies international classifications for analysis and exchange. Terminology and classification are related but not interchangeable.

## Coding layers

1. Preserve original text exactly.
2. Preserve the original Read v2 or CTV3 code and release when present.
3. Resolve the historical code through an authorised NHS Read-to-SNOMED CT map.
4. Retain SNOMED CT as the principal clinical terminology.
5. Derive ICD-10 using the national SNOMED CT-to-ICD-10 map where applicable.
6. Add ICD-11 MMS through the WHO service as a separate, versioned classification when a reviewed mapping is available.

Every code records its system and version. Every transition records map identifier, map version, relationship and mapping advice. Multiple targets and non-equivalent mappings are retained for review rather than collapsed.

## Prohibited shortcuts

- Do not infer a code from free text without recording the method and human-review state.
- Do not map ICD back to SNOMED CT: classification-to-terminology reversal loses information and is not supported by the NHS national maps.
- Do not use a language model as the authoritative terminology mapper.
- Do not discard deprecated source codes after migration.
- Do not treat ICD-10 and ICD-11 codes as automatically equivalent.

## Services and assets

- NHS England Terminology Server for SNOMED CT, dm+d, ICD-10, Read histories and FHIR ConceptMaps.
- NHS Data Migration Workbench / authorised national mapping assets for Read migration.
- WHO ICD API v2 for versioned ICD-11 MMS lookup.

Licensing and access restrictions for terminology distributions must be respected; mappings should be referenced or obtained at build/runtime rather than copied into the public repository.
