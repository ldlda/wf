from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from wf_server import build_local_static_workflow_server

from .app import create_rpc_app

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def serve(
    store_root: Path = typer.Option(
        ...,
        "--store-root",
        help="Directory containing workflow artifact, draft, and run stores.",
    ),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port", min=1, max=65535),
) -> None:
    """Serve the local/static WorkflowApi over JSON-RPC HTTP."""
    server = build_local_static_workflow_server(store_root)
    rpc_app = create_rpc_app(server)
    uvicorn.run(rpc_app, host=host, port=port, access_log=False)


def main() -> None:
    app()
