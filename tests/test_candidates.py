from pathlib import Path

from systmonline_fhir.candidates import (
    FhirExpandCandidateProvider,
    SearchCandidate,
    propose_candidates,
)
from systmonline_fhir.parser import RecordEvent
from systmonline_fhir.store import RecordStore
from systmonline_fhir.terminology import SNOMED_CT, Coding


class FakeProvider:
    name = "synthetic-candidate-provider"
    version = "synthetic-1"

    def search(self, text: str, *, limit: int) -> tuple[SearchCandidate, ...]:
        assert text == "Synthetic description"
        return (
            SearchCandidate(Coding(SNOMED_CT, "100", "Synthetic description", self.version), 1, True),
            SearchCandidate(Coding(SNOMED_CT, "200", "Related description", self.version), 2, False),
        )[:limit]


def test_candidates_are_always_proposed_review_items(tmp_path: Path):
    store = RecordStore(tmp_path / "records.sqlite3")
    source = b"synthetic"
    digest = store.retain_capture(source, "https://example.invalid")
    event = RecordEvent(
        "2026-01-01", "Example", "Example", "Coded entry", "Synthetic description", "page.html", digest
    )
    store.add_event(event, "0.4.0")

    result = propose_candidates(store, FakeProvider())

    assert result == {
        "searched": 1,
        "proposed": 2,
        "coded_entries": 1,
        "with_candidates": 1,
        "without_candidates": 0,
        "ambiguous": 1,
    }
    queue = store.review_queue()
    assert [row["status"] for row in queue] == ["proposed", "proposed"]
    assert [row["confidence"] for row in queue] == [0.4, 0.7]
    assert len(store.pending_coding_review()) == 2
    store.close()


def test_fhir_expand_adapter_uses_only_snomed_candidates():
    requests: list[tuple[str, dict[str, str]]] = []

    def transport(url: str, headers: dict[str, str]) -> dict:
        requests.append((url, headers))
        return {
            "expansion": {
                "contains": [
                    {"system": SNOMED_CT, "code": "100", "display": "Exact text"},
                    {"system": "https://example.invalid/local", "code": "X", "display": "Local"},
                ]
            }
        }

    provider = FhirExpandCandidateProvider(
        "https://terminology.example/fhir",
        "http://snomed.info/sct?fhir_vs",
        transport,
        version="synthetic-edition",
        authorization="Bearer synthetic",
    )
    candidates = provider.search("Exact text", limit=5)
    assert len(candidates) == 1
    assert candidates[0].exact_display_match
    assert "ValueSet/$expand?" in requests[0][0]
    assert requests[0][1]["Authorization"] == "Bearer synthetic"
