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


@dataclass(frozen=True)
class TestResultDetail:
    clinician_viewed: str
    result_type: str
    tests: str
    filed_by: str
    result: str
    follow_up_action: str
    source_file: str
    source_sha256: str


@dataclass(frozen=True)
class LaboratoryObservation:
    name: str
    value: float
    comparator: str
    unit: str
    reference_low: float | None
    reference_high: float | None
    narrative: str


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

    entry_types = {
        "attachment",
        "blood pressure",
        "coded entry",
        "communication",
        "drug sensitivity",
        "letter",
        "medication",
        "medication template",
        "note",
        "problem",
        "recall",
        "referral out",
        "test request",
        "test result",
        "vaccination",
    }
    tables = soup.select("main table") or soup.select("table")

    def entry_score(table) -> int:
        return sum(
            1
            for row in table.select("tr")
            if (cells := row.select(":scope > td"))
            and _clean(cells[0].get_text(" ", strip=True)).casefold() in entry_types
        )

    record_table = max(tables, key=entry_score, default=None)
    if record_table is None or entry_score(record_table) == 0:
        return []

    for row in record_table.select("tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.select(":scope > td")]
        if len(cells) >= 3 and (parsed := _date(cells[0])):
            context = (parsed, cells[1], cells[2])
            continue
        if (
            context
            and len(cells) >= 2
            and cells[0].casefold() in entry_types
            and cells[1]
        ):
            events.append(RecordEvent(*context, cells[0], cells[1], path.name, digest))
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


TEST_DETAIL_LABELS = {
    "clinician viewed": "clinician_viewed",
    "result type": "result_type",
    "tests": "tests",
    "filed by": "filed_by",
    "result": "result",
    "follow up action": "follow_up_action",
}


def parse_test_result_detail(path: Path) -> TestResultDetail | None:
    raw, digest = _source(path)
    soup = BeautifulSoup(raw, "html.parser")
    values: dict[str, str] = {}
    for row in soup.select("main table tr"):
        cells = row.select(":scope > td")
        if len(cells) != 2:
            continue
        label = _clean(cells[0].get_text(" ", strip=True)).casefold()
        field = TEST_DETAIL_LABELS.get(label)
        if field:
            values[field] = _clean(cells[1].get_text(" ", strip=True))
    if not all(field in values for field in TEST_DETAIL_LABELS.values()):
        return None
    return TestResultDetail(
        **values,
        source_file=path.name,
        source_sha256=digest,
    )


LAB_RESULT = re.compile(
    r"^(?P<name>[A-Z][^;]*?)\s+(?P<comparator>[<>]?)"
    r"(?P<value>-?\d+(?:\.\d+)?)"
    r"(?:\s+(?P<unit>[A-Za-zµμ%][A-Za-z0-9µμ/%^²·.-]*))?"
    r"(?:\s*\[(?P<low>-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*"
    r"(?P<high>-?\d+(?:\.\d+)?)\])?"
    r"(?:;\s*(?P<narrative>.*))?$"
)


def parse_pathology_observations(path: Path) -> list[LaboratoryObservation]:
    """Parse only explicit numeric rows in the retained Pathology Investigations block."""
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    main = soup.find("main")
    if main is None:
        return []
    lines = [_clean(str(child)) for child in main.children if isinstance(child, str) and _clean(str(child))]
    try:
        start = next(i for i, line in enumerate(lines) if line.casefold() == "pathology investigations") + 1
        end = next(i for i, line in enumerate(lines[start:], start) if line.casefold() == "general information")
    except StopIteration:
        return []
    observations: list[LaboratoryObservation] = []
    for line in lines[start:end]:
        match = LAB_RESULT.match(line)
        if match:
            observations.append(LaboratoryObservation(
                name=match.group("name").strip(), value=float(match.group("value")),
                comparator=match.group("comparator"), unit=match.group("unit") or "",
                reference_low=float(match.group("low")) if match.group("low") else None,
                reference_high=float(match.group("high")) if match.group("high") else None,
                narrative=(match.group("narrative") or "").strip(),
            ))
        elif observations and (line[:1].islower() or line[:1].isdigit()):
            previous = observations[-1]
            observations[-1] = LaboratoryObservation(
                **{**asdict(previous), "narrative": " ".join(filter(None, [previous.narrative, line]))}
            )
    return observations


def pathology_events(path: Path, index_event: RecordEvent, detail: TestResultDetail) -> list[RecordEvent]:
    events: list[RecordEvent] = []
    for observation in parse_pathology_observations(path):
        fields = [
            f"Test: {observation.name}", f"Value: {observation.comparator}{observation.value:g}",
            f"Unit: {observation.unit}" if observation.unit else "Unit: not supplied",
            f"Panel: {detail.tests}",
        ]
        if observation.reference_low is not None and observation.reference_high is not None:
            fields.extend([f"Reference low: {observation.reference_low:g}", f"Reference high: {observation.reference_high:g}"])
        if observation.narrative:
            fields.append(f"Source interpretation: {observation.narrative}")
        events.append(RecordEvent(index_event.date, detail.filed_by or "Not supplied by source view", "Not supplied by source view", "Laboratory observation", "; ".join(fields), path.name, detail.source_sha256))
    return events


def parse_patient_record_observations(path: Path) -> list[RecordEvent]:
    """Recover explicit numeric laboratory lines embedded in the longitudinal record."""
    raw, digest = _source(path)
    soup = BeautifulSoup(raw, "html.parser")
    context: tuple[str, str, str] | None = None
    events: list[RecordEvent] = []
    entry_types = {"coded entry", "test result"}
    for row in soup.select("main table tr"):
        cells = row.select(":scope > td")
        plain = [_clean(cell.get_text(" ", strip=True)) for cell in cells]
        if len(plain) >= 3 and (parsed := _date(plain[0])):
            context = (parsed, plain[1], plain[2])
            continue
        if not context or len(cells) < 2 or plain[0].casefold() not in entry_types:
            continue
        for line in (_clean(value) for value in cells[1].get_text("\n", strip=True).splitlines()):
            match = LAB_RESULT.match(line)
            if not match or match.group("name").rstrip().endswith(":"):
                continue
            unit = match.group("unit") or ""
            if not unit and "ratio" not in match.group("name").casefold():
                continue
            fields = [
                f"Test: {match.group('name').strip()}",
                f"Value: {match.group('comparator')}{float(match.group('value')):g}",
                f"Unit: {unit}" if unit else "Unit: not supplied",
                "Source section: Patient Record",
            ]
            if match.group("low") and match.group("high"):
                fields.extend([f"Reference low: {float(match.group('low')):g}", f"Reference high: {float(match.group('high')):g}"])
            if match.group("narrative"):
                fields.append(f"Source interpretation: {match.group('narrative').strip()}")
            events.append(RecordEvent(*context, "Laboratory observation", "; ".join(fields), path.name, digest))
    return events


def link_test_result_detail(
    index_event: RecordEvent, detail: TestResultDetail
) -> tuple[RecordEvent, float, list[str]]:
    expected_type = index_event.text.split(" — ", 1)[0]
    types_match = _clean(expected_type).casefold() == _clean(detail.result_type).casefold()
    confidence = 0.99 if types_match else 0.6
    notes = [
        "Detail linked to index by capture order; source does not repeat the opaque result identifier"
    ]
    if not types_match:
        notes.append("Result type does not match the corresponding index entry")
    text = "; ".join(
        f"{label}: {value}"
        for label, value in (
            ("Result type", detail.result_type),
            ("Tests", detail.tests),
            ("Result", detail.result),
            ("Follow up action", detail.follow_up_action),
            ("Clinician viewed", detail.clinician_viewed),
        )
        if value
    )
    event = RecordEvent(
        index_event.date,
        detail.filed_by or "Not supplied by source view",
        "Not supplied by source view",
        "Test result",
        text,
        detail.source_file,
        detail.source_sha256,
    )
    return event, confidence, notes


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
