from __future__ import annotations

import ast
from pathlib import Path


def test_wf_api_has_no_wf_mcp_imports() -> None:
    """wf_api must not import any wf_mcp modules."""
    wf_api_root = Path(__file__).resolve().parents[2] / "src" / "wf_api"
    violations: list[str] = []

    for py_file in sorted(wf_api_root.rglob("*.py")):
        rel = py_file.relative_to(wf_api_root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module == "wf_mcp" or node.module.startswith("wf_mcp."):
                    violations.append(
                        f"{module}:{node.lineno}: from {node.module} import ..."
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "wf_mcp" or alias.name.startswith("wf_mcp."):
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_api imports wf_mcp — this breaks the dependency direction rule:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
