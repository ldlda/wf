from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from .broker import (
    build_service_from_config,
    load_broker_config,
    run_broker_server,
    run_transparent_proxy_server,
)
from .server import run_unified_proxy_server


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
    serve.add_argument(
        "--mode",
        default="proxy",
        choices=["broker", "proxy", "unified"],
        help="Run broker mode, transparent proxy mode, or unified mode.",
    )
    serve.add_argument(
        "--resources-as-tools",
        action="store_true",
        help="Expose proxied resources through list_resources/read_resource tools.",
    )
    serve.add_argument(
        "--prompts-as-tools",
        action="store_true",
        help="Expose proxied prompts through list_prompts/get_prompt tools.",
    )
    serve.add_argument(
        "--search-tools",
        action="store_true",
        help="Collapse a large tool catalog into a search interface, for discovery on demand",
    )
    serve.add_argument(
        "--no-admin-tools",
        dest="admin_tools",
        action="store_false",
        help="Hide wf.admin.* tools in unified mode.",
    )
    serve.set_defaults(admin_tools=True)

    subparsers.add_parser("connections", help="List configured connections.")
    subparsers.add_parser("status", help="Show connection status and snapshot counts.")
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


async def _refresh_all(service, connection_id: str | None) -> list[dict[str, Any]]:
    target_ids = (
        [connection_id]
        if connection_id is not None
        else [connection.id for connection in service.connections.list_enabled()]
    )
    results: list[dict[str, Any]] = []
    for target_id in target_ids:
        try:
            await service.refresh_connection_catalog(target_id)
            snapshot = service.get_connection_snapshot(target_id)
            results.append(
                {
                    "connection_id": target_id,
                    "refreshed": snapshot is not None,
                    "node_count": 0 if snapshot is None else len(snapshot.nodes),
                    "resource_count": 0
                    if snapshot is None
                    else len(snapshot.resources),
                    "prompt_count": 0 if snapshot is None else len(snapshot.prompts),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "connection_id": target_id,
                    "refreshed": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        if args.mode == "proxy":
            run_transparent_proxy_server(
                args.config,
                args.transport,
                resources_as_tools=args.resources_as_tools,
                prompts_as_tools=args.prompts_as_tools,
                search_tools=args.search_tools,
            )
        elif args.mode == "broker":
            run_broker_server(args.config, args.transport)
        else:
            config = load_broker_config(args.config)
            run_unified_proxy_server(
                config,
                args.transport,
                config_path=args.config,
                resources_as_tools=args.resources_as_tools,
                prompts_as_tools=args.prompts_as_tools,
                search_tools=args.search_tools,
                admin_tools=args.admin_tools,
            )
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

    if args.command == "status":
        _json_dump(service.connection_statuses())
        return 0

    if args.command == "catalog":
        _json_dump(service.get_catalog().as_payload())
        return 0

    if args.command == "refresh":
        results = asyncio.run(_refresh_all(service, args.connection_id))
        _json_dump(
            {
                "results": results,
                "catalog": service.get_catalog().as_payload(),
            }
        )
        if any(not result["refreshed"] for result in results):
            return 1
        return 0

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
