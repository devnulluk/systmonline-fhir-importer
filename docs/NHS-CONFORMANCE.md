# NHS and UK Core conformance

## Baseline

- Base specification: HL7 FHIR R4 4.0.1.
- UK baseline: UK Core Implementation Guide STU2 2.0.1.
- Package: `fhir.r4.ukcore.stu2#2.0.1`.
- Canonical profiles: `https://fhir.hl7.org.uk/StructureDefinition/UKCore-*`.

UK Core is used as the principal representation wherever its published profiles cover the source concept. A bare base-FHIR resource is permitted only when STU2 2.0.1 has no applicable profile; each exception must remain visible and tested.

## Terminology

Prefer source codes when SystmOnline exposes them. UK clinical concepts should use SNOMED CT; medicines should use dm+d. Human-readable text must be retained even when no trustworthy code is available. The importer must never invent a code from prose. NHS-number handling will follow the UK Core Patient identifier rules and will be optional in public/synthetic fixtures.

## Validation gates

1. Parse source into a lossless canonical record with page checksum.
2. Validate JSON against FHIR R4.
3. Validate profiled resources with the HL7 FHIR Validator and `fhir.r4.ukcore.stu2#2.0.1`.
4. Treat errors as blockers; review warnings rather than hiding them globally.
5. Keep terminology validation results with the import manifest.
6. Require human review before loading a new mapper's output into the personal record.

The HL7 validator is a development/CI dependency rather than an application runtime dependency. This keeps the importer small while retaining an authoritative conformance gate.

## Dependencies

- `beautifulsoup4`: parsing saved HTML without browser/session coupling.
- HL7 FHIR Validator CLI: base FHIR and UK Core profile validation.
- UK Core package `fhir.r4.ukcore.stu2#2.0.1`: NHS profile definitions and terminology bindings.
- SNOMED CT and dm+d terminology services: required when coded source content becomes available.

Versions are pinned at conformance boundaries. Upgrades require a changelog review, regenerated fixtures and a full validation run.

## Genomics

Genomic data will use a separate evidence-aware model. UK Core profiles will be used for covered clinical resources, and emerging NHS genomic-reporting standards will be evaluated before adopting custom profiles. Raw variants, interpretations and clinical assertions must remain distinct; interpretation must record source, genome build, transcript, evidence level and review date.
