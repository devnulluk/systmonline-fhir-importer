from __future__ import annotations

import json
import re
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


def _source(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    return raw, sha256(raw).hexdigest()


def _clean(value: str) -> str:
    return " ".join(value.split())


def _event(
    path: Path,
    digest: str,
    *,
    event_date: str,
    entry_type: str,
    text: str,
    author: str = "Not supplied by source view",
    organisation: str = "Not supplied by source view",
) -> RecordEvent:
    return RecordEvent(
        event_date,
        author,
        organisation,
        entry_type,
        text,
        path.name,
        digest,
    )


def parse_patient_record(path: Path) -> list[RecordEvent]:
    raw, digest = _source(path)
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


SUMMARY_TYPES = {
    "allergies and sensitivities": "Drug sensitivity",
    "acute medication (issued in the last 12 months)": "Medication",
    "current repeat medication": "Medication",
    "past repeat medication (discontinued in the last 6 months)": "Medication",
}


def parse_summary_record(path: Path) -> list[RecordEvent]:
    raw, digest = _source(path)
    soup = BeautifulSoup(raw, "html.parser")
    events: list[RecordEvent] = []
    for heading in soup.select("main h2, main h3"):
        section = _clean(heading.get_text(" ", strip=True)).casefold()
        entry_type = SUMMARY_TYPES.get(section)
        table = heading.find_next("table")
        if not entry_type or table is None:
            continue
        for row in table.select("tr"):
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in row.select(":scope > td")]
            if len(cells) < 2 or not cells[1]:
                continue
            event_date = _date(cells[0]) or "unknown"
            events.append(
                _event(
                    path,
                    digest,
                    event_date=event_date,
                    entry_type=entry_type,
                    text=cells[1],
                )
            )
    return events


def parse_test_results_index(path: Path) -> list[RecordEvent]:
    raw, digest = _source(path)
    soup = BeautifulSoup(raw, "html.parser")
    events: list[RecordEvent] = []
    for table in soup.select("main table"):
        headers = [_clean(cell.get_text(" ", strip=True)).casefold() for cell in table.select("th")]
        if headers[:3] != ["date", "result type", "details"]:
            continue
        for row in table.select("tr"):
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in row.select(":scope > td")]
            if len(cells) < 3 or not (event_date := _date(cells[0])):
                continue
            text = " — ".join(value for value in cells[1:3] if value)
            events.append(
                _event(
                    path,
                    digest,
                    event_date=event_date,
                    entry_type="Test result index",
                    text=text,
                )
            )
    return events


def parse_supported_view(path: Path) -> tuple[str, list[RecordEvent]]:
    """Identify a saved SystmOnline view and use only its matching parser."""
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    headings = " ".join(
        _clean(heading.get_text(" ", strip=True)).casefold()
        for heading in soup.select("main h1, main h2, main h3")
    )
    if "summary patient record" in headings:
        return "summary_patient_record", parse_summary_record(path)
    if "childhood vaccinations" in headings:
        return "childhood_vaccinations", parse_childhood_vaccinations(path)
    if "test results" in headings:
        return "test_results_index", parse_test_results_index(path)
    if "patient record" in headings:
        return "patient_record", parse_patient_record(path)
    return "unsupported", []


DATE_FRAGMENT = re.compile(r"\b(?:\d{1,2}\s+[A-Za-z]{3}\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})\b")


def parse_childhood_vaccinations(path: Path) -> list[RecordEvent]:
    raw, digest = _source(path)
    soup = BeautifulSoup(raw, "html.parser")
    events: list[RecordEvent] = []
    for table in soup.select("main table"):
        headers = [_clean(cell.get_text(" ", strip=True)) for cell in table.select("th")]
        if not headers or headers[0].casefold() != "vaccination":
            continue
        for row in table.select("tr"):
            cells = row.select(":scope > td")
            if len(cells) != len(headers):
                continue
            vaccination = _clean(cells[0].get_text(" ", strip=True))
            if not vaccination:
                continue
            for age, cell in zip(headers[1:], cells[1:], strict=True):
                value = _clean(cell.get_text(" ", strip=True))
                accessible = _clean(" ".join(image.get("alt", "") for image in cell.select("img")))
                evidence = " ".join(part for part in (value, accessible) if part)
                if not evidence or evidence.casefold() in {"-", "not given", "not recorded"}:
                    continue
                match = DATE_FRAGMENT.search(evidence)
                event_date = _date(match.group(0)) if match else None
                events.append(
                    _event(
                        path,
                        digest,
                        event_date=event_date or "unknown",
                        entry_type="Vaccination",
                        text=f"{vaccination}; schedule: {age}; source status: {evidence}",
                    )
                )
    return events


def write_canonical(events: list[RecordEvent], destination: Path) -> None:
    destination.write_text(json.dumps([event.as_dict() for event in events], indent=2), encoding="utf-8")
