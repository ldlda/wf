from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Exact temporary exceptions to the wf_sources_mcp -> wf_mcp import boundary.
# Keep this empty unless a compatibility seam truly cannot live on the wf_mcp
# side. Values must name the removal condition, not just restate the exception.
ALLOWED_WF_MCP_IMPORTS: dict[tuple[str, str], str] = {}

WF_SOURCES_MCP_ROOT = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"


@dataclass(frozen=True, slots=True)
class ImportViolation:
    module: str
    line: int
    imported: str
    statement: str

    def format(self) -> str:
        return f"{self.module}:{self.line}: {self.statement}"


def _module_name(py_file: Path) -> str:
    rel = py_file.relative_to(WF_SOURCES_MCP_ROOT.parent)
    return str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")


def _is_allowed(module: str, imported: str) -> bool:
    return (module, imported) in ALLOWED_WF_MCP_IMPORTS


def _collect_forbidden_imports(
    *,
    forbidden_exact: Iterable[str] = (),
    forbidden_prefixes: Iterable[str] = (),
) -> list[ImportViolation]:
    exact = set(forbidden_exact)
    prefixes = tuple(forbidden_prefixes)
    violations: list[ImportViolation] = []

    def is_forbidden(imported: str) -> bool:
        return imported in exact or imported.startswith(prefixes)

    for py_file in sorted(WF_SOURCES_MCP_ROOT.rglob("*.py")):
        module = _module_name(py_file)
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported = node.module
                if is_forbidden(imported) and not _is_allowed(module, imported):
                    violations.append(
                        ImportViolation(
                            module=module,
                            line=node.lineno,
                            imported=imported,
                            statement=f"from {imported} import ...",
                        )
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if is_forbidden(imported) and not _is_allowed(module, imported):
                        violations.append(
                            ImportViolation(
                                module=module,
                                line=node.lineno,
                                imported=imported,
                                statement=f"import {imported}",
                            )
                        )

    return violations


def _assert_no_forbidden_imports(
    message: str,
    *,
    forbidden_exact: Iterable[str] = (),
    forbidden_prefixes: Iterable[str] = (),
) -> None:
    violations = _collect_forbidden_imports(
        forbidden_exact=forbidden_exact,
        forbidden_prefixes=forbidden_prefixes,
    )

    assert violations == [], (
        message
        + "\n"
        + "\n".join(f"  {violation.format()}" for violation in violations)
    )


def test_wf_sources_mcp_does_not_import_frontend_mcp_modules() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp imports frontend/proxy MCP modules:",
        forbidden_prefixes=(
            "wf_mcp.admin_surface",
            "wf_mcp.workflow_surface",
            "wf_mcp.server",
            "wf_mcp.proxy",
            "wf_mcp.cli",
        ),
    )


def test_wf_sources_mcp_does_not_import_wf_mcp_catalog_dtos() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp catalog DTO modules:",
        forbidden_exact={
            "wf_mcp.broker.catalog",
            "wf_mcp.capabilities",
            "wf_mcp.catalog",
            "wf_mcp.catalog.models",
        },
    )


def test_wf_sources_mcp_does_not_import_old_sdk_protocol_modules() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp SDK/runtime protocol modules:",
        forbidden_exact={
            "wf_mcp.sdk",
            "wf_mcp.sdk.adapter",
            "wf_mcp.sdk.base",
            "wf_mcp.runtime",
            "wf_mcp.runtime.protocols",
        },
    )


def test_wf_sources_mcp_does_not_import_old_sdk_converter_module() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp SDK converter module:",
        forbidden_exact={"wf_mcp.sdk.converters"},
    )


def test_wf_sources_mcp_does_not_import_old_broker_discovery_module() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp broker discovery module:",
        forbidden_exact={"wf_mcp.broker.discovery"},
    )


def test_wf_sources_mcp_does_not_import_old_workflow_wrapper_module() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp workflow wrapper module:",
        forbidden_exact={"wf_mcp.workflow", "wf_mcp.workflow.wrappers"},
    )


def test_wf_sources_mcp_does_not_import_old_broker_event_modules() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp broker event modules:",
        forbidden_exact={"wf_mcp.events", "wf_mcp.broker.events"},
    )


def test_wf_sources_mcp_does_not_import_old_broker_service_adapter_module() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp broker service adapter module:",
        forbidden_exact={"wf_mcp.broker.service.adapters"},
    )


def test_wf_sources_mcp_does_not_import_old_wf_mcp_id_modules() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports old wf_mcp source ID modules:",
        forbidden_exact={"wf_mcp.connections", "wf_mcp.shared.names"},
    )


def test_wf_sources_mcp_does_not_import_wf_mcp_broker_dtos() -> None:
    _assert_no_forbidden_imports(
        "wf_sources_mcp still imports wf_mcp broker DTO modules:",
        forbidden_exact={"wf_mcp.models", "wf_mcp.broker.models"},
    )
