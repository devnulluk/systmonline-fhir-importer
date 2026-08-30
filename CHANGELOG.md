# Changelog

## 0.3.0

- Add format-specific Summary Patient Record, Childhood Vaccinations and Test Results index parsers.
- Add mixed-view auto-detection and per-page reconciliation reports.
- Separate test-result listings from verified result-detail Observations.
- Add idempotent, revision-aware derived-event storage and review queues.
- Deduplicate identical derived FHIR resources while retaining and reporting duplicate source evidence.
- Add automated FHIR R4 and UK Core STU2 validation in continuous integration.
- Add a capture-manifest integrity verifier for backup and tamper checks.

## 0.2.0

- Add source-first paginated capture with rate limiting and safety limits.
- Retain checksummed pages and partial manifests before inspection.
- Stop safely on session expiry, HTTP errors and pagination loops.

## 0.1.0

- Initial source-preserving parser, FHIR mapping, terminology model and SQLite evidence store.
