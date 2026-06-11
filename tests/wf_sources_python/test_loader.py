from __future__ import annotations

import pytest

from wf_sources_python import load_python_source


def test_load_python_source_from_sequence_registry() -> None:
    source = load_python_source(
        source_id="local.ops",
        module="tests.fixtures.python_source_ops",
        registry="registry",
    )

    assert source.id == "local.ops"
    assert source.kind == "python"
    assert set(source.capabilities.node_specs) == {
        "local.ops.echo",
        "local.ops.upper",
    }
    assert source.permissions.safe_for_workflow is True


def test_load_python_source_rejects_missing_registry() -> None:
    with pytest.raises(ValueError, match="missing registry object"):
        load_python_source(
            source_id="local.ops",
            module="tests.fixtures.python_source_ops",
            registry="missing",
        )


def test_load_python_source_rejects_non_node_spec() -> None:
    with pytest.raises(TypeError, match="expected NodeSpec"):
        load_python_source(
            source_id="local.ops",
            module="math",
            registry="pi",
        )
