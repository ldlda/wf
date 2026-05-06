from __future__ import annotations

import re
from collections.abc import Iterable

from .refs import StepRef, step_id


def slug_id(value: str) -> str:
    """Convert a display name into a stable, readable workflow step id."""
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").lower()
    return slug or "step"


def next_step_id(base: str, nodes: Iterable[StepRef]) -> str:
    """Return a stable unused step id based on the requested base name."""
    used_ids = {step_id(node) for node in nodes}
    if base not in used_ids:
        return base
    suffix = 2
    while f"{base}_{suffix}" in used_ids:
        suffix += 1
    return f"{base}_{suffix}"
