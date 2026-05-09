from __future__ import annotations

from typing import Any

from wf_authoring import NodeSpec, node, runtime_error

from .specs import qualify_spec

BUILTIN_CONNECTION_ID = "wf.std"
"""Internal source id for workflow standard-library node specs."""


def builtin_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return built-in NodeSpecs available to raw broker workflow plans."""
    specs = [
        node(
            runtime_error,
            name="runtime_error",
            description="Fail the current workflow branch with a runtime error.",
        )
    ]
    qualified_specs = [qualify_spec(BUILTIN_CONNECTION_ID, spec) for spec in specs]
    return {spec.name: spec for spec in qualified_specs}
