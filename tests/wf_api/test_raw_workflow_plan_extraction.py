from __future__ import annotations


def test_canonical_import_from_wf_api_models() -> None:
    from wf_api.models import RawWorkflowPlan

    assert RawWorkflowPlan.__name__ == "RawWorkflowPlan"


def test_compat_import_from_wf_mcp_models() -> None:
    from wf_mcp.models import RawWorkflowPlan as CompatPlan

    assert CompatPlan.__name__ == "RawWorkflowPlan"


def test_canonical_and_compat_are_identical() -> None:
    from wf_api.models import RawWorkflowPlan as Canonical
    from wf_mcp.models import RawWorkflowPlan as Compat

    assert Canonical is Compat
