from __future__ import annotations

import ast
from pathlib import Path


def _imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == module_name for alias in node.names):
                return True
    return False


def test_cli_and_mcp_tools_do_not_import_backend_adapter() -> None:
    root = Path(__file__).resolve().parents[2]

    assert not _imports_module(
        root / "src" / "wf_cli" / "context.py",
        "wf_mcp.broker.service.workflow_api_backend",
    )
    assert not _imports_module(
        root / "src" / "wf_mcp" / "workflow_surface" / "tools.py",
        "wf_mcp.broker.service.workflow_api_backend",
    )
