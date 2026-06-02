from __future__ import annotations

import ast
from pathlib import Path


def test_wf_transport_rpc_http_imports_no_wfmcp_modules() -> None:
    root = Path("src/wf_transport_rpc_http")
    violations: list[str] = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "wf_mcp" or node.module.startswith("wf_mcp."):
                    violations.append(f"{path}:{node.lineno}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "wf_mcp" or alias.name.startswith("wf_mcp."):
                        violations.append(f"{path}:{node.lineno}: import {alias.name}")

    assert violations == []
