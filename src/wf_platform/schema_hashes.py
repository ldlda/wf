from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_json_schema(schema: dict[str, Any]) -> str:
    """Return a stable hash for one JSON-compatible schema document."""
    payload = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
