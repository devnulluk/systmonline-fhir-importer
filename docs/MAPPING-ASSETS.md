# Licensed terminology mapping assets

The public repository contains no NHS terminology distribution or cross-map data. Real assets belong in an ignored private directory and remain subject to their applicable NHS, SNOMED CT and classification licences.

## Required provenance

Every imported mapping CSV requires:

- its expected SHA-256 checksum;
- a non-empty licence or entitlement identifier;
- source and target coding-system URIs;
- source and target codes and versions;
- map identifier and version;
- relationship and any mapping advice.

The loader refuses a checksum mismatch, missing licence metadata, unknown coding-system URI or incomplete mapping row.

## Supported chain

Historical primary-care coding follows:

```text
Read v2 or CTV3
        ↓ authorised NHS migration map
SNOMED CT UK Edition
        ↓ NHS national classification map
ICD-10
```

The importer rejects a direct Read-to-ICD shortcut. It returns every available path rather than silently selecting one of several targets. Ambiguous, non-equivalent or advice-bearing mappings require review.

ICD-11 is a separate, versioned WHO classification activity; it must not be inferred from ICD-10 equivalence.

## Current private-source coverage

SystmOnline labels 234 rows as **Coded entry**, but the captured rendered view exposes descriptions rather than explicitly labelled code identifiers. These rows remain exact source text with `code unavailable`. Text-to-code suggestions may be added later as experimental review candidates, never as verified source coding.
