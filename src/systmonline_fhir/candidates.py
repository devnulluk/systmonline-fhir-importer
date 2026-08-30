from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from .store import RecordStore
from .terminology import SNOMED_CT, Coding


@dataclass(frozen=True)
class SearchCandidate:
    coding: Coding
    rank: int
    exact_display_match: bool


class CandidateProvider(Protocol):
    name: str
    version: str

    def search(self, text: str, *, limit: int) -> tuple[SearchCandidate, ...]: ...


JsonTransport = Callable[[str, dict[str, str]], dict]


class FhirExpandCandidateProvider:
    """Retrieve review candidates from a configured FHIR terminology endpoint."""

    name = "fhir-valueset-expand-candidate-search"

    def __init__(
        self,
        base_url: str,
        value_set_url: str,
        transport: JsonTransport,
        *,
        version: str,
        authorization: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.value_set_url = value_set_url
        self.transport = transport
        self.version = version
        self.authorization = authorization

    def search(self, text: str, *, limit: int) -> tuple[SearchCandidate, ...]:
        query = urlencode({"url": self.value_set_url, "filter": text, "count": limit})
        headers = {"Accept": "application/fhir+json"}
        if self.authorization:
            headers["Authorization"] = self.authorization
        payload = self.transport(f"{self.base_url}/ValueSet/$expand?{query}", headers)
        contains = payload.get("expansion", {}).get("contains", [])
        normalized = " ".join(text.casefold().split())
        candidates: list[SearchCandidate] = []
        for rank, item in enumerate(contains[:limit], start=1):
            code = item.get("code")
            display = item.get("display")
            system = item.get("system") or SNOMED_CT
            if not code or system != SNOMED_CT:
                continue
            exact = isinstance(display, str) and " ".join(display.casefold().split()) == normalized
            candidates.append(
                SearchCandidate(Coding(SNOMED_CT, str(code), display, self.version), rank, exact)
            )
        return tuple(candidates)


def propose_candidates(
    store: RecordStore,
    provider: CandidateProvider,
    *,
    limit: int = 5,
) -> dict[str, int]:
    if limit < 1 or limit > 20:
        raise ValueError("candidate limit must be between 1 and 20")
    searched = 0
    proposed = 0
    for event_id, event in store.current_events_with_ids():
        if event.entry_type.casefold() != "coded entry":
            continue
        searched += 1
        for candidate in provider.search(event.text, limit=limit):
            confidence = 0.7 if candidate.exact_display_match else 0.4
            store.add_coding(
                event_id,
                candidate.coding,
                status="proposed",
                confidence=confidence,
                method=f"{provider.name}; version={provider.version}; rank={candidate.rank}",
            )
            proposed += 1
    summary = store.candidate_summary()
    return {"searched": searched, "proposed": proposed, **summary}
