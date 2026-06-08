from __future__ import annotations

import ast
from pathlib import Path

# Temporary low-level wf_mcp imports are allowed for connection id parsing,
# reserved names, and broker DTO conversion. Catalog DTOs should now be local
# to wf_sources_mcp. Frontend/proxy/workflow-surface imports are forbidden
# because wf_sources_mcp is upstream-source code.
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


def test_wf_sources_mcp_does_not_import_wf_mcp_catalog_dtos() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {
        "wf_mcp.broker.catalog",
        "wf_mcp.capabilities",
        "wf_mcp.catalog",
        "wf_mcp.catalog.models",
    }
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp catalog DTO modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_sdk_protocol_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {
        "wf_mcp.sdk",
        "wf_mcp.sdk.adapter",
        "wf_mcp.sdk.base",
        "wf_mcp.runtime",
        "wf_mcp.runtime.protocols",
    }
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp SDK/runtime protocol modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_sdk_converter_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {
        "wf_mcp.sdk.converters",
    }
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp SDK converter module:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_broker_discovery_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.broker.discovery"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp broker discovery module:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_workflow_wrapper_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.workflow", "wf_mcp.workflow.wrappers"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp workflow wrapper module:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_broker_event_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.events", "wf_mcp.broker.events"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp broker event modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_broker_service_adapter_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.broker.service.adapters"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp broker service adapter module:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_old_wf_mcp_id_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.connections", "wf_mcp.shared.names"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(
                    f"{module}:{node.lineno}: from {node.module} import ..."
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp source ID modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_wf_mcp_broker_dtos() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.models", "wf_mcp.broker.models"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(f"{module}:{node.lineno}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(f"{module}:{node.lineno}: import {alias.name}")

    assert violations == [], (
        "wf_sources_mcp still imports wf_mcp broker DTO modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
