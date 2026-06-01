from __future__ import annotations

import wf_api.run_lifecycle as canonical
import wf_mcp.workflow_surface.run_lifecycle as shim

_EXPECTED_SYMBOLS = [
    "create_pinned_environment",
    "has_blocking_diagnostics",
    "load_stored_run",
    "mark_resume_blocked",
    "persist_stopped_run",
    "restore_interrupted_run",
    "validate_pinned_resume_environment",
]


def test_canonical_import_exports_expected_symbols() -> None:
    for name in _EXPECTED_SYMBOLS:
        assert hasattr(canonical, name), f"missing canonical symbol: {name}"


def test_shim_import_still_works() -> None:
    for name in _EXPECTED_SYMBOLS:
        assert hasattr(shim, name), f"missing shim symbol: {name}"


def test_shim_symbols_are_identical_to_canonical() -> None:
    for name in _EXPECTED_SYMBOLS:
        assert getattr(shim, name) is getattr(canonical, name), (
            f"shim.{name} is not canonical.{name}"
        )
