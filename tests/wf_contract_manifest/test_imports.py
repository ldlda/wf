from __future__ import annotations

import subprocess
import sys


def test_package_import_keeps_server_stack_lazy() -> None:
    script = """
import sys
import wf_contract_manifest

assert "wf_server" not in sys.modules
assert "wf_transport_rpc_http" not in sys.modules
assert callable(wf_contract_manifest.generate_manifest)
assert "wf_server" in sys.modules
assert "wf_transport_rpc_http" in sys.modules
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
