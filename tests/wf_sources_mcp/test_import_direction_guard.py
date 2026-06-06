from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_WF_MCP_PREFIXES = (
    "wf_mcp.admin_surface",
    "wf_mcp.workflow_surface",
    "wf_mcp.server",
    "wf_mcp.proxy",
    "wf_mcp.cli",
)


def test_wf_sources_mcp_does_not_import_frontend_mcp_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith(FORBIDDEN_WF_MCP_PREFIXES):
                    violations.append(
                        f"{module}:{node.lineno}: from {node.module} import ..."
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_WF_MCP_PREFIXES):
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp imports frontend/proxy MCP modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
