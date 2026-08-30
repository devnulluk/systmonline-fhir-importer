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
CREATE TABLE IF NOT EXISTS coding_review (
    id INTEGER PRIMARY KEY,
    assertion_id INTEGER NOT NULL REFERENCES coding_assertion(id),
    created_at TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('verified', 'rejected')),
    reviewer TEXT NOT NULL,
    notes TEXT NOT NULL,
    UNIQUE(assertion_id, created_at)
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
        existing = self.connection.execute(
            """SELECT id FROM parsed_event
            WHERE capture_sha256 = ? AND source_file = ? AND event_date = ? AND author = ?
              AND organisation = ? AND entry_type = ? AND source_text = ? AND parser_version = ?""",
            (
                event.source_sha256,
                event.source_file,
                event.date,
                event.author,
                event.organisation,
                event.entry_type,
                event.text,
                parser_version,
            ),
        ).fetchone()
        if existing:
            self.connection.execute(
                "UPDATE parsed_event SET parse_confidence = ?, parse_notes = ? WHERE id = ?",
                (confidence, json.dumps(notes or []), int(existing[0])),
            )
            self.connection.commit()
            return int(existing[0])
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
        existing = self.connection.execute(
            """SELECT id FROM coding_assertion
            WHERE event_id = ? AND system = ? AND code = ? AND version IS ? AND status = ?""",
            (event_id, coding.system, coding.code, coding.version, status),
        ).fetchone()
        if existing:
            self.connection.execute(
                """UPDATE coding_assertion
                SET display = ?, confidence = ?, method = ?, mapping_provenance = ?,
                    review_required = ? WHERE id = ?""",
                (
                    coding.display,
                    confidence,
                    method,
                    json.dumps(provenance),
                    int(review_required),
                    int(existing[0]),
                ),
            )
            self.connection.commit()
            return int(existing[0])
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

    def pending_coding_review(self) -> list[dict]:
        rows = self.connection.execute(
            """SELECT coding_assertion.*, parsed_event.source_text
            FROM coding_assertion
            JOIN parsed_event ON parsed_event.id = coding_assertion.event_id
            WHERE (coding_assertion.review_required = 1 OR coding_assertion.confidence < 1)
              AND NOT EXISTS (
                  SELECT 1 FROM coding_review WHERE coding_review.assertion_id = coding_assertion.id
              )
            ORDER BY coding_assertion.confidence ASC, coding_assertion.id"""
        ).fetchall()
        return [dict(row) for row in rows]

    def review_coding(
        self,
        assertion_id: int,
        *,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> int:
        if decision not in {"verified", "rejected"}:
            raise ValueError("coding review decision must be verified or rejected")
        if not reviewer.strip():
            raise ValueError("coding review requires a reviewer")
        exists = self.connection.execute(
            "SELECT 1 FROM coding_assertion WHERE id = ?", (assertion_id,)
        ).fetchone()
        if not exists:
            raise ValueError("coding assertion does not exist")
        cursor = self.connection.execute(
            """INSERT INTO coding_review
            (assertion_id, created_at, decision, reviewer, notes) VALUES (?, ?, ?, ?, ?)""",
            (
                assertion_id,
                datetime.now(UTC).isoformat(),
                decision,
                reviewer,
                notes,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def event_review_queue(self) -> list[dict]:
        rows = self.connection.execute(
            """WITH ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY capture_sha256, source_file, event_date, author,
                                 organisation, entry_type, source_text
                    ORDER BY id DESC
                ) AS revision_rank
                FROM parsed_event
            )
            SELECT * FROM ranked
            WHERE revision_rank = 1 AND (parse_confidence < 1 OR parse_notes != '[]')
            ORDER BY parse_confidence ASC, id"""
        ).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in (
                "raw_capture",
                "parsed_event",
                "coding_assertion",
                "coding_review",
                "analysis_finding",
            )
        }

    def events(self) -> list[RecordEvent]:
        rows = self.connection.execute(
            """WITH ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY capture_sha256, source_file, event_date, author,
                                 organisation, entry_type, source_text
                    ORDER BY id DESC
                ) AS revision_rank
                FROM parsed_event
            )
            SELECT event_date, author, organisation, entry_type, source_text,
                   source_file, capture_sha256
            FROM ranked WHERE revision_rank = 1 ORDER BY event_date, id"""
        ).fetchall()
        return [
            RecordEvent(
                row["event_date"],
                row["author"],
                row["organisation"],
                row["entry_type"],
                row["source_text"],
                row["source_file"],
                row["capture_sha256"],
            )
            for row in rows
        ]

    def current_events_with_ids(self) -> list[tuple[int, RecordEvent]]:
        rows = self.connection.execute(
            """WITH ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY capture_sha256, source_file, event_date, author,
                                 organisation, entry_type, source_text
                    ORDER BY id DESC
                ) AS revision_rank
                FROM parsed_event
            )
            SELECT id, event_date, author, organisation, entry_type, source_text,
                   source_file, capture_sha256
            FROM ranked WHERE revision_rank = 1 ORDER BY event_date, id"""
        ).fetchall()
        return [
            (
                int(row["id"]),
                RecordEvent(
                    row["event_date"],
                    row["author"],
                    row["organisation"],
                    row["entry_type"],
                    row["source_text"],
                    row["source_file"],
                    row["capture_sha256"],
                ),
            )
            for row in rows
        ]

    def candidate_summary(self) -> dict[str, int]:
        coded_event_ids = [
            event_id
            for event_id, event in self.current_events_with_ids()
            if event.entry_type.casefold() == "coded entry"
        ]
        if not coded_event_ids:
            return {"coded_entries": 0, "with_candidates": 0, "without_candidates": 0, "ambiguous": 0}
        placeholders = ",".join("?" for _ in coded_event_ids)
        rows = self.connection.execute(
            f"""SELECT event_id, count(*) AS candidate_count FROM coding_assertion
            WHERE status = 'proposed' AND event_id IN ({placeholders}) GROUP BY event_id""",
            coded_event_ids,
        ).fetchall()
        counts = {int(row["event_id"]): int(row["candidate_count"]) for row in rows}
        return {
            "coded_entries": len(coded_event_ids),
            "with_candidates": sum(count > 0 for count in counts.values()),
            "without_candidates": len(coded_event_ids) - len(counts),
            "ambiguous": sum(count > 1 for count in counts.values()),
        }
