from __future__ import annotations

from pathlib import Path

from examples.rpc_cli_smoke import (
    SmokeIds,
    build_workflow_config,
    parse_json_stdout,
)


def test_build_workflow_config_targets_rpc_server(tmp_path: Path) -> None:
    config = build_workflow_config(store_root=tmp_path / "store", port=9876)

    assert config["version"] == 1
    assert config["client"]["target"]["kind"] == "rpc_http"
    assert config["client"]["target"]["url"] == "http://127.0.0.1:9876/rpc"
    assert config["server"]["store"] == {
        "kind": "filesystem",
        "root": str(tmp_path / "store"),
    }
    assert config["server"]["transports"] == [
        {"kind": "rpc_http", "host": "127.0.0.1", "port": 9876}
    ]


def test_smoke_ids_are_namespaced_by_suffix() -> None:
    ids = SmokeIds.from_suffix("abc123")

    assert ids.workspace_id == "smoke_ws_abc123"
    assert ids.artifact_id == "smoke_artifact_abc123"
    assert ids.deployment_id == "smoke_deploy_abc123"


def test_parse_json_stdout_ignores_surrounding_whitespace() -> None:
    payload = parse_json_stdout('  {"run_id": "run_1"}\n')

    assert payload == {"run_id": "run_1"}


def test_parse_json_stdout_reports_command_context() -> None:
    try:
        parse_json_stdout("not json", command=("wf", "status"))
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert "wf status" in message
    assert "did not return valid JSON" in message
