from __future__ import annotations

from collections.abc import Iterable

from .entries import EXPLAIN_CARDS
from .models import ExplainCard, ExplainSummary


class UnknownExplainCode(KeyError):
    """Raised when a diagnostic code is not present in the curated registry."""


class ExplainRegistry:
    """Exact-match registry for docs-backed explanation cards."""

    def __init__(self, entries: Iterable[ExplainCard] = EXPLAIN_CARDS) -> None:
        self._entries = {entry.code: entry for entry in entries}

    def get(self, code: str) -> ExplainCard:
        """Return a full explanation card for one stable code."""
        try:
            return self._entries[code]
        except KeyError as exc:
            raise UnknownExplainCode(code) from exc

    def list_entries(self) -> list[ExplainSummary]:
        """Return lean summaries for discovery output."""
        return [
            ExplainSummary(code=entry.code, summary=entry.summary)
            for entry in self._entries.values()
        ]


DEFAULT_EXPLAIN_REGISTRY = ExplainRegistry()
