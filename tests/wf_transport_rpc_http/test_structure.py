from __future__ import annotations

import importlib
from pathlib import Path


def test_rpc_transport_has_domain_method_modules() -> None:
    for module_name in (
        "wf_transport_rpc_http.methods_admin",
        "wf_transport_rpc_http.methods_capabilities",
        "wf_transport_rpc_http.methods_drafts",
        "wf_transport_rpc_http.methods_artifacts",
        "wf_transport_rpc_http.methods_deployments",
        "wf_transport_rpc_http.methods_runs",
        "wf_transport_rpc_http.methods_sources",
        "wf_transport_rpc_http.methods_source_registry",
    ):
        module = importlib.import_module(module_name)

        assert hasattr(module, "register_methods")


def test_rpc_transport_client_stays_thin() -> None:
    client_path = Path("src/wf_transport_rpc_http/client.py")
    line_count = len(client_path.read_text(encoding="utf-8").splitlines())

    assert line_count < 140
