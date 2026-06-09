from __future__ import annotations

import json

from typer.testing import CliRunner

from wf_cli.app import app
from wf_cli.commands.status import _payload_count


def test_wf_status_local_static_target(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {
                    "store": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "store"),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "--local",
            "status",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target"]["mode"] == "local"
    assert payload["target"]["config_path"] == str(config_path)
    assert payload["target"]["url"] is None
    assert payload["workflow"]["capability_count"] >= 1
    assert "wf.std.constant" in payload["workflow"]["sample_capabilities"]
    assert payload["sources"]["available"] is True
    assert payload["sources"]["source_count"] >= 1
    assert payload["admin"]["available"] is True
    assert payload["registry"]["available"] is False


def test_status_count_prefers_paged_total() -> None:
    payload = {"total": 91, "capabilities": [{"name": "first"}]}

    assert _payload_count(payload, "capabilities") == 91


def test_status_count_falls_back_to_page_length_without_total() -> None:
    payload = {"capabilities": [{"name": "first"}, {"name": "second"}]}

    assert _payload_count(payload, "capabilities") == 2
