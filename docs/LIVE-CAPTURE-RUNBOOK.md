# Authorised live-capture runbook

This runbook is for a person capturing their own authorised record. It deliberately excludes appointment, medication-request, messaging, sharing and account-management actions.

## Before login

1. Confirm the account owner has authorised unattended read-only capture.
2. Prepare a new private capture directory outside version control.
3. Confirm the previous manifest and pages still pass `systmonline-fhir-verify`.
4. Configure the history start date; `01/01/1900` is the safe full-record default.

## Patient Record

1. Open **Patient Record** from the main menu.
2. Set the start date to the agreed historical boundary.
3. Include unknown-date records.
4. Capture each rendered page once, in order, with a pause between navigation actions.
5. Record its rendered-DOM SHA-256 checksum, byte count, capture time and sequence.
6. Stop on a login page, unexpected navigation, repeated page or page-count mismatch.

## Test-result details

The Test Results search restricts each request to 60 days. The automated capture walks non-overlapping windows from today backwards to the configured history boundary, newest first. The Patient Record remains the longitudinal fallback for results whose detail report is unavailable.

The saved index currently uses one separate `POST ViewDetailedTestResult` form per listed result. Each form carries an opaque result identifier. These identifiers are sensitive session-linked source data and must not be logged or committed.

For every listed result the importer:

1. submits the page's own read-only `ViewDetailedTestResult` form inside the authenticated session;
2. captures and checksums the detail before parsing;
3. preserves the exact index/detail order;
4. reconciles the detail count against the index count and stops on mismatch.

Hidden form values exist only in memory for the active authorised session. They are never written to manifests, status output, logs, Git or Obsidian. Do not infer missing results from index text.

## Mobius / Portainer

Deploy `compose.mobius.yml` and set the credentials and portal import token in Portainer, or mount file-backed secrets and use the corresponding `*_FILE` variables. Persistent data lives at `/mnt/Mobius/docker/systmonline-fhir-importer` and includes the append-only capture directories, SQLite evidence database and a non-sensitive `status.json`.

The normal schedule is daily. A failed login, expired session, unexpected form, HTTP error or reconciliation mismatch aborts the refresh before portal upload; the last successful portal database remains in service.

## After capture

1. Write the capture-set manifest atomically.
2. Log out explicitly and confirm the logout page.
3. Verify every captured page against the manifest.
4. Retain sources in SQLite before parsing.
5. Generate reconciliation, canonical JSON and FHIR outputs.
6. Review unknown dates, duplicate rows, unsupported views and index entries without details.
7. Run the FHIR R4 and UK Core validator before any downstream import.

## Never retain

- username or password;
- cookies, tokens or browser-profile data;
- hidden session fields as diagnostic output;
- real record pages in Git, CI artifacts or the Obsidian vault.
