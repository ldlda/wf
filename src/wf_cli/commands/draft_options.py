from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from wf_api.surface import RouteSource
from wf_core.paths import LocalPath, PathResolutionError, StatePath


def _parse_assignment_flags(
    values: list[str] | None,
    *,
    option_name: str,
    expected: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values or []:
        source, separator, target = item.partition("=")
        if separator != "=" or not source or not target:
            raise typer.BadParameter(f"{option_name} must use {expected}")
        if source in parsed:
            raise typer.BadParameter(f"duplicate {option_name} for {source!r}")
        parsed[source] = target
    return parsed


def _parse_map_flags(values: list[str] | None) -> dict[str, str]:
    return _parse_assignment_flags(
        values,
        option_name="--map",
        expected="source=target",
    )


def _parse_output_map_flags(
    values: list[str] | None, *, option_name: str = "--bind-output"
) -> dict[str, str]:
    parsed = _parse_assignment_flags(
        values,
        option_name=option_name,
        expected="LOCAL_OUTPUT=STATE_TARGET",
    )
    for local_output, state_target in parsed.items():
        try:
            LocalPath.parse(local_output)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"{option_name} source {local_output!r} must be a node-local "
                "output path such as value or ."
            ) from exc
        try:
            StatePath.parse(state_target)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"{option_name} target {state_target!r} must be a state path "
                "such as state.value"
            ) from exc
    return parsed


def _parse_step_input_map_flags(
    values: list[str] | None, *, option_name: str = "--map"
) -> dict[str, str]:
    """Parse graph-source to bare-local input mappings for one draft step."""
    parsed = _parse_assignment_flags(
        values,
        option_name=option_name,
        expected="GRAPH_SOURCE=LOCAL_TARGET",
    )
    for source, target in parsed.items():
        if target.startswith("local."):
            bare_target = target.removeprefix("local.")
            raise typer.BadParameter(
                f"{option_name} target must be a bare local field; "
                f"use {source}={bare_target}, not {source}={target}"
            )
    return parsed


def _parse_route_flags(values: list[str] | None) -> dict[str, str]:
    return _parse_assignment_flags(
        values,
        option_name="--route",
        expected="OUTCOME=TARGET",
    )


def parse_json_file(path: Path, *, option_name: str) -> Any:
    """Read one structured CLI value and report file/JSON failures as option errors."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.BadParameter(f"{option_name}: cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"{option_name}: invalid JSON in {path}: {exc.msg}"
        ) from exc


def route_source(from_step: str | None, from_outcome: str | None) -> RouteSource | None:
    if from_step is None:
        if from_outcome is not None:
            raise typer.BadParameter("--from-outcome requires --from-step")
        return None
    return RouteSource(step_id=from_step, outcome=from_outcome or "ok")
