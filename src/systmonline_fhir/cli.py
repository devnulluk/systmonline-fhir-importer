from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fhir import bundle
from .parser import write_canonical
from .pipeline import ingest_saved_pages, ingest_supported_views
from .store import RecordStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert saved SystmOnline record pages to FHIR R4 JSON")
    parser.add_argument("pages", nargs="+", type=Path)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--fhir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--auto-detect", action="store_true")
    parser.add_argument("--reconciliation", type=Path)
    args = parser.parse_args()
    store = RecordStore(args.database)
    try:
        if args.auto_detect:
            events = ingest_supported_views(
                args.pages, store, report_path=args.reconciliation
            )
            write_canonical(events, args.canonical)
            args.fhir.write_text(json.dumps(bundle(events), indent=2), encoding="utf-8")
        else:
            events = ingest_saved_pages(
                args.pages, store, canonical_path=args.canonical, fhir_path=args.fhir
            )
    finally:
        store.close()
    print(f"Converted {len(events)} events; review outputs before importing.")


if __name__ == "__main__":
    main()
