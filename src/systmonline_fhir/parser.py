from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from time import strptime

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class RecordEvent:
    date: str
    author: str
    organisation: str
    entry_type: str
    text: str
    source_file: str
    source_sha256: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _date(value: str) -> str | None:
    value = " ".join(value.split())
    for fmt in ("%d %b %Y", "%d/%m/%Y"):
        try:
            parsed = strptime(value, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
        except ValueError:
            pass
    return None


def parse_patient_record(path: Path) -> list[RecordEvent]:
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    soup = BeautifulSoup(raw, "html.parser")
    events: list[RecordEvent] = []
    context: tuple[str, str, str] | None = None

    for row in soup.select("tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.select(":scope > td")]
        if len(cells) >= 3 and (parsed := _date(cells[0])):
            context = (parsed, cells[1], cells[2])
            continue
        if context and len(cells) >= 2 and cells[0] and cells[1]:
            events.append(RecordEvent(*context, cells[0], cells[1], path.name, digest))
            context = None
    return events


def write_canonical(events: list[RecordEvent], destination: Path) -> None:
    destination.write_text(json.dumps([event.as_dict() for event in events], indent=2), encoding="utf-8")
