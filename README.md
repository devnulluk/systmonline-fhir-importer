# SystmOnline FHIR Importer

An experimental, source-preserving importer for personal GP records viewed through SystmOnline. It converts locally saved patient-record pages into a reviewable canonical JSON file and an NHS-aligned FHIR R4 collection Bundle.

It also accepts Patients Know Best FHIR R4 Bundles. The complete Bundle is retained before supported resources and source codings are added to the same evidence database. See [Patients Know Best support](docs/PATIENTS-KNOW-BEST.md).

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

Licensed mapping files are checksum-pinned and kept private; see [Mapping assets](docs/MAPPING-ASSETS.md). Version 0.4.0 also reports explicit-code coverage without printing clinical text and refuses to invent a code from an unlabelled description.

The [experimental candidate workflow](docs/EXPERIMENTAL-CANDIDATES.md) can retrieve ranked SNOMED CT suggestions through a configured FHIR terminology endpoint, but all suggestions remain low-confidence proposals with append-only human review.

Raw captured pages are retained byte-for-byte in the importer database before parsing. Derived events and coding assertions carry confidence, method and review state; anything below 100% confidence is highlighted automatically. See [Data trust model](docs/DATA-TRUST-MODEL.md).

See [Capture and reconciliation](docs/CAPTURE-AND-RECONCILIATION.md) for the private-evidence boundary, safe stopping conditions, duplicate handling and clinical-completeness states.

The [authorised live-capture runbook](docs/LIVE-CAPTURE-RUNBOOK.md) defines the read-only browser boundary and the next test-result-detail capture procedure.

## Runtime credentials

The unattended capture runtime accepts either direct environment variables or file-backed secrets. File-backed values take precedence and are recommended for Mobius:

```text
SYSTMONLINE_USERNAME_FILE=/run/secrets/systmonline_username
SYSTMONLINE_PASSWORD_FILE=/run/secrets/systmonline_password
```

For a simpler Portainer deployment, the fallback is:

```text
SYSTMONLINE_USERNAME=your-username
SYSTMONLINE_PASSWORD=your-password
```

Do not set real values in Compose files, Git, shell command arguments or Obsidian. A configured `*_FILE` that is missing or empty causes startup to fail; it never silently falls back to the less secure environment value. Credential objects redact both fields from their representation, and errors name only the missing setting.

Version 0.7.0 adds authenticated read-only capture for an authorised personal account. It deliberately supports SystmOnline's JavaScript/POST pagination rather than assuming ordinary links. The Patient Record is requested from `SYSTMONLINE_HISTORY_START` (default `01/01/1900`) through today with unknown-date entries included. Test Results are searched newest-first in complete, non-overlapping 60-day windows and every listed detail is retained in index order.

Every response is saved and checksummed before parsing. Manifests contain filenames, checksums, sizes, timestamps and date windows, but never credentials, cookies, session UUIDs or opaque result identifiers. Re-running is safe: raw captures and derived records are content-addressed/idempotent and older snapshots are not deleted.

Run one refresh locally:

```text
systmonline-fhir-sync
```

Or deploy [compose.mobius.yml](compose.mobius.yml) in Portainer. The container has no published port, writes only below `/data`, runs without root privileges and refreshes every 24 hours by default. The first successful run performs the complete backfill; later runs refresh a 120-day overlap so late amendments are retained without repeating hundreds of historical searches. Set `CLINICAL_IMPORT_URL` and `CLINICAL_IMPORT_TOKEN` to upload the reconciled database to the private portal after a successful capture. See the [live-capture runbook](docs/LIVE-CAPTURE-RUNBOOK.md).

Saved pages can be ingested into the evidence database and exported together:

```text
systmonline-fhir saved-page-*.html \
  --database private/records.sqlite3 \
  --canonical private/canonical.json \
  --fhir private/bundle.json
```

Import a PKB FHIR Bundle into the same evidence database:

```text
pkb-fhir-import private/pkb-bundle.json \
  --database private/records.sqlite3 \
  --source-uri pkb-fhir-export
```

For a mixed capture set, add `--auto-detect` and `--reconciliation private/reconciliation.json`. The importer selects a parser from the page's own heading rather than its filename.

Verify the private evidence set before or after a backup:

```text
systmonline-fhir-verify private/capture-set-manifest.json
```

Export only the current parser revision of each logical event:

```text
systmonline-fhir-export \
  --database private/records.sqlite3 \
  --canonical private/canonical-current.json \
  --fhir private/bundle-current.json
```

The pipeline retains each source page first, verifies that the parser saw the same SHA-256 content, then stores derived events and writes the reviewable exports.

Version 0.3.0 adds format-specific parsing for the Summary Patient Record, Childhood Vaccinations and Test Results index. Index listings are deliberately represented as reviewable source facts rather than final clinical Observations until their detail pages have been captured. Reimports are idempotent and produce a per-page reconciliation report with unknown-date and review counts.

Detailed result pages can now be parsed and reconciled to their index entries. Because the detail view does not repeat SystmOnline's opaque result identifier, linkage uses capture order plus an exact result-type cross-check and remains visibly marked at 99% confidence. It is never silently described as certain.

Continuous integration validates a synthetic bundle with the HL7-maintained validator against FHIR R4 4.0.1 and `fhir.r4.ukcore.stu2#2.0.1`. Real records never enter CI or the repository.

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
