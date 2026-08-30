from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import create_rpc_app

from .model import ContractManifest
from .normalize import manifest_from_openrpc


def generate_manifest() -> ContractManifest:
    """Compose the real server against an isolated store and normalize OpenRPC."""
    with TemporaryDirectory(prefix="wf-contract-manifest-") as directory:
        # The checked contract describes the complete opt-in API. Product
        # composition remains draft-free by default; contract generation is
        # the deliberate compatibility seam that asks for the full surface.
        server = build_local_static_workflow_server(
            Path(directory) / "store", drafts=True
        )
        document = cast(
            dict[str, object], create_rpc_app(server, drafts=True).get_openrpc()
        )
        # Normalization deliberately drops framework metadata that could carry
        # process-local paths or transport details.
        return manifest_from_openrpc(document)
