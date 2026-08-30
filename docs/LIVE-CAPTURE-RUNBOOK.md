# Authorised live-capture runbook

This runbook is for a person capturing their own authorised record. It deliberately excludes appointment, medication-request, messaging, sharing and account-management actions.

## Before login

1. Obtain immediate user confirmation before transmitting credentials.
2. Prepare a new private capture directory outside version control.
3. Confirm the previous manifest and pages still pass `systmonline-fhir-verify`.
4. Record the intended read-only views and a maximum page count.

## Patient Record

1. Open **Patient Record** from the main menu.
2. Set the start date to the agreed historical boundary.
3. Include unknown-date records.
4. Capture each rendered page once, in order, with a pause between navigation actions.
5. Record its rendered-DOM SHA-256 checksum, byte count, capture time and sequence.
6. Stop on a login page, unexpected navigation, repeated page or page-count mismatch.

## Test-result details

The saved index currently uses one separate `POST ViewDetailedTestResult` form per listed result. Each form carries an opaque result identifier. These identifiers are sensitive session-linked source data and must not be logged or committed.

For every listed result:

1. Select its visible **View Result** control in the authorised browser.
2. Capture the rendered detail page and checksum it before parsing.
3. Return using the page's ordinary read-only return control.
4. Confirm the index position before advancing.
5. Reconcile captured detail pages against the index count.

Do not replay hidden form values outside the authorised browser session. Do not infer missing results from index text.

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
