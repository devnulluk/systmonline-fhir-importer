from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .store import RecordStore
from .terminology import extract_explicit_codings


def terminology_coverage(database: Path) -> dict:
    store = RecordStore(database)
    try:
        events = [event for event in store.events() if event.entry_type.casefold() == "coded entry"]
    finally:
        store.close()
    systems: Counter[str] = Counter()
    explicit_entries = 0
    for event in events:
        codings = extract_explicit_codings(event.text)
        if codings:
            explicit_entries += 1
            systems.update(coding.system for coding in codings)
    return {
        "coded_entry_rows": len(events),
        "rows_with_explicit_codes": explicit_entries,
        "rows_without_explicit_codes": len(events) - explicit_entries,
        "explicit_codes_by_system": dict(sorted(systems.items())),
        "policy": "Unlabelled descriptions are preserved as text and are not guessed into a coding system",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report explicit-code coverage without printing clinical text")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = terminology_coverage(args.database)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
