"""Neutral run-wide step budget value model.

`RunLimits` is immutable policy captured when a run is created. It lives
here (next to `run_state`, not under `runtime`) so `run_state` can import
it at module top without executing the `wf_core.runtime` package whose
engine imports `run_state` back. Admission policy stays in
`wf_core.runtime.limits`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunLimits:
    """Immutable step budget captured when a run is created."""

    max_steps: int = 10_000

    def __post_init__(self) -> None:
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int):
            raise TypeError("max_steps must be an integer")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")


__all__ = ["RunLimits"]
