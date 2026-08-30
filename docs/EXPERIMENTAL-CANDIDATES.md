# Experimental terminology candidates

Free-text terminology search is a review aid, not an authoritative map.

## Hard boundaries

- Candidate search never changes source text.
- Every retrieved concept is stored with status `proposed`.
- An exact display match is capped at 70% confidence.
- A non-exact retrieval candidate is capped at 40% confidence.
- Multiple returned concepts make the source entry explicitly ambiguous.
- Search rank and terminology-edition version are retained.
- A candidate cannot enter a verified clinical export without an append-only human review decision.
- AI or text similarity cannot supply the identity of a source Read, CTV3 or SNOMED code.

## NHS Terminology Server adapter

The adapter uses the standard FHIR `ValueSet/$expand` boundary with a configured SNOMED CT value-set URL, edition version, result limit and transport. Authentication is injected at runtime and must never be written to configuration, logs or the repository.

No live server calls occur during tests. Synthetic FHIR expansion responses verify filtering, ranking and exclusion of non-SNOMED systems.

## Review record

Approval and rejection are append-only rows containing the assertion, timestamp, decision, reviewer and notes. The original candidate assertion remains unchanged for audit. Pending-review reports exclude only assertions with an explicit recorded decision.

Clinical review should confirm concept meaning, hierarchy, context, temporality and whether a pre-coordinated or post-coordinated representation is required. A matching description alone is insufficient.
