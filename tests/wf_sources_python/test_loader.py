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


def test_load_python_source_from_callable_registry() -> None:
    source = load_python_source(
        source_id="local.ops",
        module="tests.fixtures.python_source_ops",
        registry="callable_registry",
    )

    assert set(source.capabilities.node_specs) == {
        "local.ops.echo",
        "local.ops.upper",
    }


def test_load_python_source_propagates_enabled_flag() -> None:
    source = load_python_source(
        source_id="local.ops",
        module="tests.fixtures.python_source_ops",
        registry="registry",
        enabled=False,
    )

    assert source.enabled is False


def test_load_python_source_rejects_duplicate_qualified_names() -> None:
    with pytest.raises(ValueError, match="duplicate NodeSpec names"):
        load_python_source(
            source_id="local.ops",
            module="tests.fixtures.python_source_ops",
            registry="duplicate_registry",
        )


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
