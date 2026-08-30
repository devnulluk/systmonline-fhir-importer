from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fhir import bundle
from .parser import write_canonical
from .store import RecordStore


def export_current(database: Path, canonical: Path, fhir: Path) -> int:
    store = RecordStore(database)
    try:
        events = store.events()
    finally:
        store.close()
    write_canonical(events, canonical)
    fhir.write_text(json.dumps(bundle(events), indent=2), encoding="utf-8")
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the current derived event revisions")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--fhir", type=Path, required=True)
    args = parser.parse_args()
    count = export_current(args.database, args.canonical, args.fhir)
    print(f"Exported {count} current events; review and validate before downstream import.")


if __name__ == "__main__":
    main()
