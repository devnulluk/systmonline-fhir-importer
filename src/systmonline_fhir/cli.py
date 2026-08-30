from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import ingest_saved_pages
from .store import RecordStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert saved SystmOnline record pages to FHIR R4 JSON")
    parser.add_argument("pages", nargs="+", type=Path)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--fhir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    store = RecordStore(args.database)
    try:
        events = ingest_saved_pages(
            args.pages, store, canonical_path=args.canonical, fhir_path=args.fhir
        )
    finally:
        store.close()
    print(f"Converted {len(events)} events; review outputs before importing.")


if __name__ == "__main__":
    main()
