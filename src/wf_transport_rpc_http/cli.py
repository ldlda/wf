from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from wf_config import (
    FilesystemStoreConfig,
    RpcHttpTransportConfig,
    load_workflow_config,
)

from wf_server import build_local_static_workflow_server

from .app import create_rpc_app

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def serve(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to neutral workflow config JSON.",
    ),
    store_root: Path | None = typer.Option(
        None,
        "--store-root",
        help="Override filesystem workflow store root.",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        help="Override RPC bind host; defaults to config or 127.0.0.1.",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        min=1,
        max=65535,
        help="Override RPC bind port; defaults to config or 8765.",
    ),
) -> None:
    """Serve the local/static WorkflowApi over JSON-RPC HTTP."""
    resolved_store_root = store_root
    resolved_host = host
    resolved_port = port
    resolved_rpc_path = "/rpc"
    if config is not None:
        workflow_config = load_workflow_config(config)
        store = workflow_config.server.store
        if not isinstance(store, FilesystemStoreConfig):
            raise typer.BadParameter(
                "wf-rpc-server currently requires filesystem store"
            )
        resolved_store_root = resolved_store_root or store.root
        rpc_transport = next(
            (
                transport
                for transport in workflow_config.server.transports
                if isinstance(transport, RpcHttpTransportConfig)
            ),
            None,
        )
        if rpc_transport is not None:
            resolved_host = host or rpc_transport.host
            resolved_port = port or rpc_transport.port
            resolved_rpc_path = rpc_transport.path
    if resolved_store_root is None:
        raise typer.BadParameter(
            "--store-root is required when --config is not supplied"
        )

    server = build_local_static_workflow_server(resolved_store_root)
    rpc_app = create_rpc_app(server, rpc_path=resolved_rpc_path)
    uvicorn.run(
        rpc_app,
        host=resolved_host or "127.0.0.1",
        port=resolved_port or 8765,
        access_log=False,
    )


def main() -> None:
    app()
