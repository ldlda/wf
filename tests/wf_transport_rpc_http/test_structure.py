from __future__ import annotations

import importlib
import inspect
import pkgutil

import wf_transport_rpc_http.client as rpc_client_package
from wf_transport_rpc_http.client import RpcWorkflowApiClient
from wf_transport_rpc_http.client.base import RpcCaller, RpcClientTransport


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


def test_rpc_client_mixins_share_one_call_contract() -> None:
    call_owners = {
        RpcClientTransport._call,
        RpcCaller._call,
    }

    for module_info in pkgutil.iter_modules(rpc_client_package.__path__):
        if module_info.name in {"__init__", "base"}:
            continue
        module = importlib.import_module(
            f"wf_transport_rpc_http.client.{module_info.name}"
        )
        for _name, value in inspect.getmembers(module, inspect.isclass):
            if value.__module__ == module.__name__:
                assert "_call" not in value.__dict__

    assert len(call_owners) == 2
