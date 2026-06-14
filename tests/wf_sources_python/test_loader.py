from __future__ import annotations

from pathlib import Path

import pytest

from wf_sources_python import PythonSourceProvider, load_python_source


class PythonSourceConfigFixture:
    id = "local.ops"
    path = Path(".")
    module = "tests.fixtures.python_source_ops"
    registry = "registry"
    enabled = True


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


def test_python_source_provider_loads_configured_sources() -> None:
    sources = PythonSourceProvider([PythonSourceConfigFixture()]).load_sources()

    assert set(sources) == {"local.ops"}
    assert "local.ops.echo" in sources["local.ops"].capabilities.node_specs


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


def test_load_python_source_uses_configured_import_path(tmp_path: Path) -> None:
    source_root = tmp_path / "source_root"
    source_root.mkdir()
    (source_root / "project_ops.py").write_text(
        """
from __future__ import annotations

from pydantic import BaseModel
from wf_authoring import node

class EchoInput(BaseModel):
    text: str

class EchoOutput(BaseModel):
    echoed: str

@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(echoed=payload.text)

registry = [echo]
""",
        encoding="utf-8",
    )

    source = load_python_source(
        source_id="local.ops",
        path=source_root,
        module="project_ops",
        registry="registry",
    )

    assert set(source.capabilities.node_specs) == {"local.ops.echo"}


def test_load_python_source_isolates_same_module_name_across_roots(
    tmp_path: Path,
) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()
    source_template = """
from __future__ import annotations

from pydantic import BaseModel
from wf_authoring import node

class Input(BaseModel):
    text: str

class Output(BaseModel):
    value: str

@node(name="{name}")
def operation(payload: Input) -> Output:
    return Output(value=payload.text)

registry = [operation]
"""
    (left_root / "ops.py").write_text(
        source_template.format(name="left"), encoding="utf-8"
    )
    (right_root / "ops.py").write_text(
        source_template.format(name="right"), encoding="utf-8"
    )

    left = load_python_source(
        source_id="local.left",
        path=left_root,
        module="ops",
        registry="registry",
    )
    right = load_python_source(
        source_id="local.right",
        path=right_root,
        module="ops",
        registry="registry",
    )

    assert set(left.capabilities.node_specs) == {"local.left.left"}
    assert set(right.capabilities.node_specs) == {"local.right.right"}


def test_load_python_source_supports_relative_imports_under_source_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "relative_source"
    package_root = source_root / "pkg"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "labels.py").write_text(
        'LABEL = "relative"\n',
        encoding="utf-8",
    )
    (package_root / "ops.py").write_text(
        """
from __future__ import annotations

from pydantic import BaseModel
from wf_authoring import node

from .labels import LABEL

class Input(BaseModel):
    text: str

class Output(BaseModel):
    value: str

@node(name=LABEL)
def operation(payload: Input) -> Output:
    return Output(value=payload.text)

registry = [operation]
""",
        encoding="utf-8",
    )

    source = load_python_source(
        source_id="local.relative",
        path=source_root,
        module="pkg.ops",
        registry="registry",
    )

    assert set(source.capabilities.node_specs) == {"local.relative.relative"}


def test_load_python_source_supports_delayed_relative_imports(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "delayed_relative_source"
    package_root = source_root / "pkg"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "labels.py").write_text(
        'LABEL = "delayed"\n',
        encoding="utf-8",
    )
    (package_root / "registry.py").write_text(
        """
def build_registry():
    from .ops import operation

    return [operation]
""",
        encoding="utf-8",
    )
    (package_root / "ops.py").write_text(
        """
from __future__ import annotations

from pydantic import BaseModel
from wf_authoring import node

from .labels import LABEL

class Input(BaseModel):
    text: str

class Output(BaseModel):
    value: str

@node(name=LABEL)
def operation(payload: Input) -> Output:
    return Output(value=payload.text)
""",
        encoding="utf-8",
    )

    source = load_python_source(
        source_id="local.delayed",
        path=source_root,
        module="pkg.registry",
        registry="build_registry",
    )

    assert set(source.capabilities.node_specs) == {"local.delayed.delayed"}


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
