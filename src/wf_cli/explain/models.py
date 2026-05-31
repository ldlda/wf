from __future__ import annotations

from pydantic import BaseModel, Field


class ExplainCard(BaseModel):
    """Human-curated help for one stable workflow diagnostic/error code."""

    code: str = Field(min_length=1, description="Stable diagnostic or CLI error code.")
    summary: str = Field(min_length=1, description="One-sentence explanation.")
    why_it_happens: list[str] = Field(
        min_length=1,
        description="Common causes, ordered from most likely to least likely.",
    )
    how_to_fix: list[str] = Field(
        min_length=1, description="Concrete next steps an agent or user can try."
    )
    related_docs: list[str] = Field(
        default_factory=list,
        description="Documentation resource IDs or file references.",
    )


class ExplainSummary(BaseModel):
    """Lean index entry for `wf explain --list`."""

    code: str = Field(min_length=1)
    summary: str = Field(min_length=1)
