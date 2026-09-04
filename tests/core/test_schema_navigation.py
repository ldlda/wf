from __future__ import annotations

from wf_core.schema_navigation import SchemaNavigator


def test_array_type_does_not_require_an_items_schema() -> None:
    """Unconstrained array elements do not make the collection non-array."""
    view = SchemaNavigator({"type": "array"}).root

    assert view.is_array()
