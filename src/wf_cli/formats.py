from __future__ import annotations

import json
from enum import StrEnum
from typing import Any


class ListOutputFormat(StrEnum):
    """Output formats allowed for list/discovery commands."""

    JSON = "json"
    IDS = "ids"
    COMPACT = "compact"


def render_list_payload(
    payload: dict[str, Any],
    *,
    collection_key: str,
    output_format: ListOutputFormat,
    id_field: str,
    summary_fields: tuple[str, ...] = (),
) -> str:
    """Render a handler list payload without changing the JSON contract."""
    if output_format is ListOutputFormat.JSON:
        return json.dumps(payload, indent=2, sort_keys=True)
    items = payload.get(collection_key, [])
    if not isinstance(items, list):
        raise ValueError(f"list payload missing array field {collection_key!r}")
    if output_format is ListOutputFormat.IDS:
        return "\n".join(_item_id(item, id_field=id_field) for item in items)
    return "\n".join(
        _compact_line(item, id_field=id_field, summary_fields=summary_fields)
        for item in items
    )


def emit_list_payload(
    payload: dict[str, Any],
    *,
    collection_key: str,
    output_format: ListOutputFormat,
    id_field: str,
    summary_fields: tuple[str, ...] = (),
) -> None:
    """Print a list payload in the requested CLI list format."""
    print(
        render_list_payload(
            payload,
            collection_key=collection_key,
            output_format=output_format,
            id_field=id_field,
            summary_fields=summary_fields,
        )
    )


def _item_id(item: object, *, id_field: str) -> str:
    if not isinstance(item, dict):
        return str(item)
    value = item.get(id_field)
    return "" if value is None else str(value)


def _compact_line(
    item: object,
    *,
    id_field: str,
    summary_fields: tuple[str, ...],
) -> str:
    if not isinstance(item, dict):
        return str(item)
    parts = [_item_id(item, id_field=id_field)]
    for field in summary_fields:
        if field in item and item[field] is not None:
            parts.append(f"{field}={item[field]}")
    return "\t".join(parts)
