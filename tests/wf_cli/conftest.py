from __future__ import annotations

import json
from pathlib import Path


def write_python_source_config(
    root: Path,
    *,
    target: dict[str, object] | None = None,
) -> Path:
    """Write a temporary Python source config with a ``local.ops`` source.

    Returns the path to the written ``wf.json`` config file.
    """
    if target is None:
        target = {
            "kind": "rpc_http",
            "url": "http://127.0.0.1:8765/rpc",
        }
    source_root = root / "source"
    source_root.mkdir()
    (source_root / "ops.py").write_text(
        """
from pydantic import BaseModel

from wf_authoring import node


class EchoInput(BaseModel):
    text: str
    path: str | None = None


class EchoOutput(BaseModel):
    text: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(text=payload.text)


registry = [echo]
""".lstrip(),
        encoding="utf-8",
    )
    config_path = root / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": target},
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": "source",
                            "module": "ops",
                            "registry": "registry",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path
