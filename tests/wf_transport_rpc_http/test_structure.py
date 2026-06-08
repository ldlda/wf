from __future__ import annotations

import importlib
import inspect

from wf_transport_rpc_http.client import RpcWorkflowApiClient


def test_rpc_transport_has_domain_method_modules() -> None:
    for module_name in (
        "wf_transport_rpc_http.methods.admin",
        "wf_transport_rpc_http.methods.capabilities",
        "wf_transport_rpc_http.methods.drafts",
        "wf_transport_rpc_http.methods.artifacts",
        "wf_transport_rpc_http.methods.deployments",
        "wf_transport_rpc_http.methods.runs",
        "wf_transport_rpc_http.methods.sources",
        "wf_transport_rpc_http.methods.source_registry",
    ):
        module = importlib.import_module(module_name)

        assert hasattr(module, "register_methods")


def test_rpc_transport_client_stays_thin() -> None:
    line_count = len(inspect.getsource(RpcWorkflowApiClient).splitlines())

    assert line_count < 40
