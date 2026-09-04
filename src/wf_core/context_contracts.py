from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

type ContextSchema = dict[str, Any]

PRIOR_OUTCOME_CONTEXT_KEY = "prior_outcome"
ACTIVATED_INCOMING_EDGE_CONTEXT_KEY = "activated_incoming_edge"
SCOPE_ID_CONTEXT_KEY = "scope_id"
LINEAGE_ID_CONTEXT_KEY = "lineage_id"
PARENT_LINEAGE_ID_CONTEXT_KEY = "parent_lineage_id"
LOOP_ITEM_CONTEXT_KEY = "loop_item"
LOOP_INDEX_CONTEXT_KEY = "loop_index"
FOREACH_CONTEXT_KEY = "foreach"


@dataclass(frozen=True, slots=True)
class ContextFieldContract:
    """Semantic contract for one key exposed by a runtime execution frame."""

    name: str
    schema: ContextSchema
    description: str


STANDARD_CONTEXT_FIELDS = (
    ContextFieldContract(
        PRIOR_OUTCOME_CONTEXT_KEY,
        {"type": ["string", "null"]},
        "Prior route outcome",
    ),
    ContextFieldContract(
        ACTIVATED_INCOMING_EDGE_CONTEXT_KEY,
        {"type": ["string", "null"]},
        "Incoming step id",
    ),
    ContextFieldContract(
        SCOPE_ID_CONTEXT_KEY,
        {"type": "string"},
        "Execution scope id",
    ),
    ContextFieldContract(
        LINEAGE_ID_CONTEXT_KEY,
        {"type": "string"},
        "Execution lineage id",
    ),
    ContextFieldContract(
        PARENT_LINEAGE_ID_CONTEXT_KEY,
        {"type": ["string", "null"]},
        "Parent lineage id",
    ),
)
STANDARD_CONTEXT_FIELD_NAMES = frozenset(
    field.name for field in STANDARD_CONTEXT_FIELDS
)
RESERVED_CONTEXT_KEYS = STANDARD_CONTEXT_FIELD_NAMES | {
    LOOP_ITEM_CONTEXT_KEY,
    LOOP_INDEX_CONTEXT_KEY,
    FOREACH_CONTEXT_KEY,
}


def foreach_context_fields(
    alias: str,
    item_schema: ContextSchema,
) -> tuple[ContextFieldContract, ...]:
    """Return the iteration keys, including a configured item alias once."""
    item_contract = ContextFieldContract(
        LOOP_ITEM_CONTEXT_KEY,
        deepcopy(item_schema),
        "Current foreach item",
    )
    index_contract = ContextFieldContract(
        LOOP_INDEX_CONTEXT_KEY,
        {"type": "integer"},
        "Current foreach item index",
    )
    fields = [item_contract, index_contract]
    if alias and alias not in RESERVED_CONTEXT_KEYS:
        fields.append(
            ContextFieldContract(
                alias,
                deepcopy(item_schema),
                "Current foreach item",
            )
        )
    return tuple(fields)


def foreach_entry_schema(node_id: str, item_schema: ContextSchema) -> ContextSchema:
    """Return the JSON schema for one structured ``foreach.<id>`` entry.

    Identity fields disclose the dynamic activation/frame/scope/lineage when
    advanced runtime code needs them; ``item`` carries the inferred
    collection item schema.
    """
    return {
        "type": "object",
        "properties": {
            "node_id": {"const": node_id},
            "activation_id": {"type": "string"},
            "frame_id": {"type": "string"},
            "scope_id": {"type": "string"},
            "lineage_id": {"type": "string"},
            "index": {"type": "integer"},
            "item": deepcopy(item_schema),
        },
        "required": [
            "node_id",
            "activation_id",
            "frame_id",
            "scope_id",
            "lineage_id",
            "index",
            "item",
        ],
        "additionalProperties": False,
    }


def structured_foreach_contract(
    entry_schemas: Mapping[str, ContextSchema],
) -> ContextFieldContract:
    """Return the ``foreach`` map contract for one static owner stack."""
    return ContextFieldContract(
        FOREACH_CONTEXT_KEY,
        {
            "type": "object",
            "properties": dict(entry_schemas),
            "required": sorted(entry_schemas),
            "additionalProperties": False,
        },
        "Structured foreach context by static node id",
    )
