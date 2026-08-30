# Data trust model

## Immutable capture

Every acquired page or export is stored byte-for-byte in `raw_capture` before parsing. Its SHA-256 digest is its identity. Repeated captures are deduplicated by digest but acquisition metadata remains part of the import manifest.

## Derived events

Parsed events retain the exact source text, source digest, parser version, parse confidence and notes. Corrections create new derived records; they do not alter the captured source.

## Coding assertions

- `source`: the code was present in the source.
- `verified`: resolved by an authoritative, versioned mapping or reviewed by a qualified person.
- `proposed`: an educated mapping hypothesis awaiting review.
- `rejected`: preserved audit evidence for a mapping that must not be used.

Anything below confidence `1.0` is automatically placed in the review queue. A proposed code is always review-required regardless of numeric confidence. Public UI and MCP results must display status, confidence, method and provenance beside it.

Only source and verified codings may populate the primary clinical `CodeableConcept.coding` list. Proposed mappings can support experimental analysis but must remain separately labelled and must not be exported as clinical truth.

## Analysis findings

Findings retain algorithm name/version, evidence references, confidence and review state. They are experimental by default. A finding never mutates a source event, verified code, diagnosis or medication.
