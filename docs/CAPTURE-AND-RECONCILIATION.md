# Capture and reconciliation

## Evidence boundary

An authenticated capture is private evidence. Captured pages, manifests, databases and generated clinical bundles belong under an ignored `private/` or `raw/` directory and must never be committed.

Browser captures are labelled `rendered_dom`. They preserve the HTML rendered in the authorised browser, but are not claimed to be byte-identical HTTP responses. Each page has a SHA-256 checksum, capture timestamp, source view and capture-kind declaration.

Credentials, cookies, tokens and browser session material are not capture artifacts.

## Safe stopping conditions

The paginated capture engine stops on:

- an expired session or returned login page;
- a non-success HTTP response;
- a repeated pagination URL;
- the configured maximum page count.

An interrupted run retains a partial manifest so its evidence can be inspected without presenting the run as complete.

## Derived records

Every source is retained before parsing. A parser must reproduce the retained SHA-256 checksum before its events may be stored. Parser revisions remain in the audit database; current exports select the latest revision of each logical event.

The reconciliation report records, per source page:

- source kind and checksum;
- parsed and unique event counts;
- exact duplicate source rows;
- events with unknown dates;
- entries requiring review.

Exact duplicate rows remain present in the captured evidence and are counted in reconciliation. The FHIR collection contains one logical resource per identical row so resource identifiers remain unique.

## Clinical completeness states

A test-results index proves only that a result is listed. It is represented as a reviewable source fact, not as a final laboratory Observation. It can become a clinical Observation only after the corresponding detail page has been captured and parsed.

Unknown dates are represented explicitly and enter the event review queue. Missing authors or organisations in a summary view are labelled `Not supplied by source view`; they are never inferred from another page.
