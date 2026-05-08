from __future__ import annotations

from wf_mcp.shared.names import (
    is_admin_tool_name,
    namespaced_tool_name,
    parse_namespaced_tool_name,
)


def test_namespaced_tool_names_are_reversible_with_known_connections() -> None:
    proxy_name = namespaced_tool_name("everything.default", "get-sum")

    parsed = parse_namespaced_tool_name(
        proxy_name,
        {"everything.default", "everything"},
    )

    assert parsed is not None
    assert parsed.proxy_name == "everything.default_get-sum"
    assert parsed.connection_id == "everything.default"
    assert parsed.local_name == "get-sum"


def test_namespaced_tool_parser_rejects_unknown_and_admin_names() -> None:
    assert parse_namespaced_tool_name("missing_echo", {"everything.default"}) is None
    assert is_admin_tool_name("wf.mcp_list_connections") is True
    assert is_admin_tool_name("everything.default_echo") is False
