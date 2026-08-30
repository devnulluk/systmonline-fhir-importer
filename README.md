# SystmOnline FHIR Importer

An experimental, source-preserving importer for personal GP records viewed through SystmOnline. It converts locally saved patient-record pages into a reviewable canonical JSON file and an NHS-aligned FHIR R4 collection Bundle.

## Principles

- The person and their longitudinal record are the centre—not the GP system.
- Original pages are preserved locally with SHA-256 provenance.
- Conversion is deterministic and safe to repeat.
- Generated FHIR is reviewed and validated before it reaches a record server.
- UK Core profiles are used whenever UK Core defines one for the resource.
- No credentials, session identifiers or real patient data belong in this repository.

## Current status

The first parser handles SystmOnline's date/author/organisation header rows followed by typed record entries. It maps problems, medication, sensitivities, vaccinations, results, blood pressure, letters and attachments to initial FHIR R4 resource shapes. Patient, condition, medication statement, allergy, immunisation and observation resources declare the UK Core STU2 2.0.1 profile. Resources for which that release has no matching profile remain base FHIR R4 and are recorded as deliberate conformance exceptions.

See [NHS and UK Core conformance](docs/NHS-CONFORMANCE.md) for the profile, terminology and validation policy.

Historical Read codes are retained and mapped through SNOMED CT before ICD classification. The mapping chain and versions remain auditable; see [Terminology and classification](docs/TERMINOLOGY.md).

Raw captured pages are retained byte-for-byte in the importer database before parsing. Derived events and coding assertions carry confidence, method and review state; anything below 100% confidence is highlighted automatically. See [Data trust model](docs/DATA-TRUST-MODEL.md).

The capture engine now follows paginated records with a configurable pause and page limit. Every HTTP response is saved and checksummed before it is inspected, including an unexpected login page. It stops safely on session expiry, HTTP errors, pagination loops or the page limit, and writes a resumable partial manifest when interrupted. Live authenticated capture is intentionally not yet enabled: that will be tested interactively without storing credentials in this repository.

Saved pages can be ingested into the evidence database and exported together:

```text
systmonline-fhir saved-page-*.html \
  --database private/records.sqlite3 \
  --canonical private/canonical.json \
  --fhir private/bundle.json
```

The pipeline retains each source page first, verifies that the parser saw the same SHA-256 content, then stores derived events and writes the reviewable exports.

## Safety boundary

This project organises a person's own records. It does not diagnose, recommend treatment, interpret genomic variants, or replace a clinician. Imported content must retain its source and be treated as unverified until reviewed.

## AI disclosure

This project is openly vibe coded. Its initial architecture, documentation, parser, FHIR mapping and tests were produced collaboratively by Mark Brown with OpenAI Codex/ChatGPT. AI-generated work is reviewed, tested and remains subject to ordinary software and clinical-safety scrutiny.

## Development

```text
python -m venv .venv
pip install -e ".[dev]"
pytest
```

Only synthetic fixtures are committed. The `raw/` and `private/` directories are ignored deliberately.

## Licence

MIT. SystmOnline and TPP are trademarks of their respective owners; this project is independent and unaffiliated.
