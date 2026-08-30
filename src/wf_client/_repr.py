"""Small, inert renderers shared by the public workflow-client snapshots.

Representations are a debugging aid, not another client operation.  This
module deliberately accepts already-loaded values and never knows about the
workflow transport port.  The same bounded projector is used for plain and
HTML representations so notebooks cannot accidentally expose an unbounded
trace, output, or credential-shaped value.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from itertools import islice

_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set_cookie",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "password",
    "api_key",
}
_MAX_DEPTH = 2
_MAX_ITEMS = 8
_MAX_STRING = 160
_MAX_RENDERED = 1_200


def _canonical_key(key: object) -> str:
    """Normalize snake/kebab/camel spellings to the shared evidence keys."""
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return value.replace(" ", "_").replace("-", "_").lower()


def _secret_key(key: object) -> bool:
    # Match the evidence policy's exact key set; substring matching would
    # incorrectly redact harmless fields such as ``tokenCount`` or ``secretary``.
    return _canonical_key(key) in _SENSITIVE_KEYS


def bounded_value(value: object, *, depth: int = 0) -> object:
    """Project loaded JSON-like data into a small, secret-safe preview."""
    if depth >= _MAX_DEPTH:
        return "[truncated]"
    if isinstance(value, str):
        return value if len(value) <= _MAX_STRING else value[:_MAX_STRING] + "…"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Mapping):
        iterator = iter(value.items())
        items = list(islice(iterator, _MAX_ITEMS + 1))
        preview = {
            str(key): "[redacted]"
            if _secret_key(key)
            else bounded_value(item, depth=depth + 1)
            for key, item in items[:_MAX_ITEMS]
        }
        if len(items) > _MAX_ITEMS:
            preview["…"] = "more entries"
        return preview
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        iterator = iter(value)
        items = list(islice(iterator, _MAX_ITEMS + 1))
        preview = [bounded_value(item, depth=depth + 1) for item in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            preview.append("… more items")
        return preview
    if isinstance(value, Sequence):
        return "[truncated sequence]"
    if hasattr(value, "__iter__"):
        iterator = iter(value)  # type: ignore[call-overload]
        items = list(islice(iterator, _MAX_ITEMS + 1))
        preview = [bounded_value(item, depth=depth + 1) for item in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            preview.append("… more items")
        return preview
    rendered = repr(value)
    return rendered if len(rendered) <= _MAX_STRING else rendered[:_MAX_STRING] + "…"


def preview(value: object) -> str:
    """Render a bounded value without allowing an object's repr to grow freely."""
    try:
        rendered = json.dumps(bounded_value(value), sort_keys=True, default=str)
    except TypeError, ValueError:
        rendered = str(bounded_value(value))
    return rendered[:_MAX_RENDERED] + ("…" if len(rendered) > _MAX_RENDERED else "")


def short_repr(type_name: str, **fields: object) -> str:
    """Build a compact Python repr from already-loaded field values."""
    body = ", ".join(f"{name}={preview(value)}" for name, value in fields.items())
    rendered = f"{type_name}({body})"
    return rendered[:_MAX_RENDERED] + ("…" if len(rendered) > _MAX_RENDERED else "")


def html_repr(type_name: str, **fields: object) -> str:
    """Build a bounded HTML table suitable for IPython rich display."""

    def html_preview(value: object) -> str:
        rendered = preview(value)
        return rendered[:400] + ("…" if len(rendered) > 400 else "")

    rows = "".join(
        '<tr><th scope="row">'
        + html.escape(name)
        + "</th><td><code>"
        + html.escape(html_preview(value))
        + "</code></td></tr>"
        for name, value in fields.items()
    )
    return (
        '<div class="wf-client-repr"><strong>'
        + html.escape(type_name)
        + "</strong><table><tbody>"
        + rows
        + "</tbody></table></div>"
    )
