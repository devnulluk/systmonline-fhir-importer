from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from .parser import RecordEvent
from .terminology import Coding, MappingStep

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS raw_capture (
    sha256 TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS parsed_event (
    id INTEGER PRIMARY KEY,
    capture_sha256 TEXT NOT NULL REFERENCES raw_capture(sha256),
    source_file TEXT NOT NULL,
    event_date TEXT NOT NULL,
    author TEXT NOT NULL,
    organisation TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    source_text TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    parse_confidence REAL NOT NULL CHECK(parse_confidence >= 0 AND parse_confidence <= 1),
    parse_notes TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS coding_assertion (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES parsed_event(id),
    system TEXT NOT NULL,
    code TEXT NOT NULL,
    display TEXT,
    version TEXT,
    status TEXT NOT NULL CHECK(status IN ('source', 'verified', 'proposed', 'rejected')),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    method TEXT NOT NULL,
    mapping_provenance TEXT NOT NULL DEFAULT '[]',
    review_required INTEGER NOT NULL CHECK(review_required IN (0, 1)),
    UNIQUE(event_id, system, code, version, status)
);
CREATE TABLE IF NOT EXISTS analysis_finding (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    method TEXT NOT NULL,
    method_version TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    evidence_references TEXT NOT NULL,
    experimental INTEGER NOT NULL DEFAULT 1 CHECK(experimental IN (0, 1)),
    review_status TEXT NOT NULL DEFAULT 'unreviewed'
);
"""


class RecordStore:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def retain_capture(
        self, content: bytes, source_uri: str, content_type: str = "text/html"
    ) -> str:
        digest = sha256(content).hexdigest()
        self.connection.execute(
            "INSERT OR IGNORE INTO raw_capture VALUES (?, ?, ?, ?, ?)",
            (digest, source_uri, datetime.now(UTC).isoformat(), content_type, content),
        )
        self.connection.commit()
        return digest

    def add_event(
        self, event: RecordEvent, parser_version: str, confidence: float = 1.0, notes: list[str] | None = None
    ) -> int:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        cursor = self.connection.execute(
            """INSERT INTO parsed_event
            (capture_sha256, source_file, event_date, author, organisation, entry_type,
             source_text, parser_version, parse_confidence, parse_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.source_sha256,
                event.source_file,
                event.date,
                event.author,
                event.organisation,
                event.entry_type,
                event.text,
                parser_version,
                confidence,
                json.dumps(notes or []),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_coding(
        self,
        event_id: int,
        coding: Coding,
        *,
        status: str,
        confidence: float,
        method: str,
        mapping_steps: tuple[MappingStep, ...] = (),
    ) -> int:
        if status not in {"source", "verified", "proposed", "rejected"}:
            raise ValueError("invalid coding status")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        review_required = status == "proposed" or confidence < 1
        provenance = [
            {
                "source": step.source.as_fhir(),
                "target": step.target.as_fhir(),
                "map_identifier": step.map_identifier,
                "map_version": step.map_version,
                "relationship": step.relationship,
                "advice": step.advice,
            }
            for step in mapping_steps
        ]
        cursor = self.connection.execute(
            """INSERT INTO coding_assertion
            (event_id, system, code, display, version, status, confidence, method,
             mapping_provenance, review_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                coding.system,
                coding.code,
                coding.display,
                coding.version,
                status,
                confidence,
                method,
                json.dumps(provenance),
                int(review_required),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def review_queue(self) -> list[dict]:
        rows = self.connection.execute(
            """SELECT coding_assertion.*, parsed_event.source_text
            FROM coding_assertion JOIN parsed_event ON parsed_event.id = coding_assertion.event_id
            WHERE review_required = 1 OR confidence < 1 ORDER BY confidence ASC, coding_assertion.id"""
        ).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in ("raw_capture", "parsed_event", "coding_assertion", "analysis_finding")
        }
