from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fhir import bundle
from .parser import parse_patient_record, write_canonical


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert saved SystmOnline record pages to FHIR R4 JSON")
    parser.add_argument("pages", nargs="+", type=Path)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--fhir", type=Path, required=True)
    args = parser.parse_args()
    events = [event for page in args.pages for event in parse_patient_record(page)]
    write_canonical(events, args.canonical)
    args.fhir.write_text(json.dumps(bundle(events), indent=2), encoding="utf-8")
    print(f"Converted {len(events)} events; review outputs before importing.")


if __name__ == "__main__":
    main()
