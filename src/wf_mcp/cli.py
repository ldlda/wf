from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from .broker_server import (
    build_service_from_config,
    load_broker_config,
    run_broker_server,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wf-mcp")
    parser.add_argument(
        "--config",
        default="wf_mcp.config.json",
        help="Path to broker config JSON.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the broker MCP server.")
    serve.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http", "streamable_http"],
        help="Transport to run the broker server with.",
    )

    subparsers.add_parser("connections", help="List configured connections.")
    subparsers.add_parser("catalog", help="Print the broker catalog as JSON.")

    refresh = subparsers.add_parser(
        "refresh",
        help="Refresh one connection catalog or all configured connections.",
    )
    refresh.add_argument("connection_id", nargs="?", help="Connection id to refresh.")

    return parser


def _service_from_config(config_path: str | Path):
    config = load_broker_config(config_path)
    return build_service_from_config(config)


def _json_dump(data: Any) -> None:
    print(json.dumps(data, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        run_broker_server(args.config, args.transport)
        return 0

    service = _service_from_config(args.config)

    if args.command == "connections":
        _json_dump(
            [
                {
                    "id": connection.id,
                    "server": connection.server,
                    "account": connection.account,
                    "enabled": connection.enabled,
                    "metadata": connection.metadata,
                }
                for connection in service.connections.list_all()
            ]
        )
        return 0

    if args.command == "catalog":
        _json_dump(service.get_catalog().as_payload())
        return 0

    if args.command == "refresh":
        if args.connection_id:
            asyncio.run(service.refresh_connection_catalog(args.connection_id))
        else:
            for connection in service.connections.list_enabled():
                asyncio.run(service.refresh_connection_catalog(connection.id))
        _json_dump(service.get_catalog().as_payload())
        return 0

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
