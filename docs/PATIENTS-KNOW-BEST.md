# Patients Know Best support

## Supported input

The importer accepts a FHIR R4 JSON `Bundle` obtained from Patients Know Best (PKB). It preserves the complete bundle byte-for-byte in `raw_capture` before deriving timeline events.

```text
pkb-fhir-import private/pkb-bundle.json \
  --database private/records.sqlite3 \
  --source-uri pkb-fhir-export
```

Supported resource types are:

- `AllergyIntolerance`
- `Appointment`
- `Condition`
- `DiagnosticReport`
- `DocumentReference`
- `Immunization`
- `MedicationRequest`
- `MedicationStatement`
- `Observation`
- `Procedure`
- `QuestionnaireResponse`

Other resources remain present in the retained raw Bundle and are reported as skipped rather than silently discarded.

FHIR codings supplied by PKB are stored as source assertions at 100% transcription confidence. This means confidence that the coding was copied accurately—not confidence that the underlying clinical statement is correct. The importer does not manufacture SNOMED CT, ICD or LOINC codes when a resource does not supply them.

## API path

PKB documents an aggregated read-only FHIR endpoint. Access requires a valid token, and its examples query patient data by an NHS-number identifier or PKB public identifier. The API returns paginated FHIR JSON Bundles. PKB also documents OAuth 2.0 for its FHIR APIs and currently coordinates endpoint access with integration customers.

The automated connector will therefore require PKB-issued integration credentials and these non-secret settings:

- production FHIR base URL;
- token endpoint;
- patient identifier system;
- enabled resource types;
- initial backfill date.

Client credentials must be supplied at runtime from a secret store. They must never appear in command arguments, logs, captured Bundles, SQLite event text, Git history or the public repository.

Until PKB grants API access, a user-provided FHIR Bundle can be imported with the command above. Browser scraping is deliberately not implemented: the standards-based export/API route provides stronger provenance and is less likely to break when the web interface changes.

## Incremental synchronization design

The future API connector will:

1. request a short-lived OAuth token;
2. fetch each supported resource with patient scope and `_lastUpdated` where supported;
3. follow Bundle pagination links only on the configured PKB host;
4. retain every response before parsing;
5. deduplicate derived events by retained content hash, FHIR resource type/id and parser version;
6. retain deleted/history semantics when exposed by the endpoint;
7. stop safely on authentication, pagination, validation or rate-limit failures;
8. update its cursor only after the entire synchronization validates;
9. notify through the existing Apprise/ntfy path on failure or stale data.

Resource-specific search parameters and coverage vary as PKB migrates data types to its FHIR-native architecture. The connector must inspect the production capability statement and record it with each synchronization rather than assuming sandbox capabilities.

## Data-quality boundary

- Original PKB JSON is evidence layer 1.
- Direct FHIR fields and codings are source facts, not inferred mappings.
- Timeline summaries are deterministic derived representations.
- Missing dates receive 90% parsing confidence and a visible review note.
- Any later cross-source reconciliation remains proposed until identifiers and clinical semantics match with documented confidence.

