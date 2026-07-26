from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from pydantic import TypeAdapter, ValidationError

from wf_api.surface import RouteSource
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, LocalPath, PathResolutionError, StatePath

_INPUT_BINDINGS_ADAPTER = TypeAdapter(list[InputBinding])
_OUTPUT_BINDINGS_ADAPTER = TypeAdapter(list[OutputBinding])


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
    """Parse graph-source to rootless node-local mappings for one draft step."""
    parsed = _parse_assignment_flags(
        values,
        option_name=option_name,
        expected="GRAPH_SOURCE=LOCAL_TARGET",
    )
    for source, target in parsed.items():
        if target.startswith("local."):
            bare_target = target.removeprefix("local.")
            raise typer.BadParameter(
                f"{option_name} target must be a rootless node-local path; "
                f"use {source}={bare_target}, not {source}={target}"
            )
        try:
            LocalPath.parse(target)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"{option_name} target must be a rootless node-local path; "
                f"got {target!r}; use report.title or ."
            ) from exc
    return parsed


def validation_error_as_bad_parameter(
    exc: ValidationError,
) -> typer.BadParameter:
    """Keep Pydantic failures on Click's concise input-error surface."""
    return typer.BadParameter(str(exc))


def parse_step_input_binding_flags(
    values: list[str] | None,
) -> list[InputPathBinding]:
    """Parse ordered step-input path bindings without collapsing source fan-out."""
    return _parse_input_path_binding_flags(
        values,
        option_name="--map",
        target_label="node-local",
    )


def parse_capability_input_binding_flags(
    values: list[str] | None,
) -> list[InputPathBinding]:
    """Parse ordered capability input paths from the public ``--input`` flag."""
    return _parse_input_path_binding_flags(
        values,
        option_name="--input",
        target_label="node-local",
    )


def _parse_input_path_binding_flags(
    values: list[str] | None,
    *,
    option_name: str,
    target_label: str,
) -> list[InputPathBinding]:
    """Parse ordered GRAPH_SOURCE=LOCAL_TARGET bindings for one CLI audience."""
    bindings: list[InputPathBinding] = []
    for item in values or []:
        source, separator, target = item.partition("=")
        if separator != "=" or not source or not target:
            raise typer.BadParameter(
                f"{option_name} must use GRAPH_SOURCE=LOCAL_TARGET"
            )
        if target.startswith("local."):
            bare_target = target.removeprefix("local.")
            raise typer.BadParameter(
                f"{option_name} target must be a rootless {target_label} path; "
                f"use {source}={bare_target}, not {source}={target}"
            )
        try:
            source_path = GraphSourcePath.parse(source)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"{option_name} source must be a graph source path: {exc}"
            ) from exc
        try:
            target_path = LocalPath.parse(target)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"{option_name} target must be a rootless {target_label} path: {exc}"
            ) from exc
        bindings.append(InputPathBinding(path=source_path, target=target_path))
    return bindings


def parse_step_input_value_flags(
    values: list[str] | None,
) -> list[InputValueBinding]:
    """Parse ordered step-input literal bindings from LOCAL_TARGET=JSON flags."""
    return _parse_input_value_binding_flags(values, target_label="node-local")


def _parse_input_value_binding_flags(
    values: list[str] | None,
    *,
    target_label: str,
) -> list[InputValueBinding]:
    """Parse ordered LOCAL_TARGET=JSON bindings for one CLI audience."""
    bindings: list[InputValueBinding] = []
    for item in values or []:
        target, separator, raw_value = item.partition("=")
        if separator != "=" or not target:
            raise typer.BadParameter("--value must use LOCAL_TARGET=JSON")
        if target.startswith("local."):
            raise typer.BadParameter(
                f"--value target must be a rootless {target_label} path"
            )
        try:
            value = json.loads(raw_value)
            bindings.append(
                InputValueBinding(target=LocalPath.parse(target), value=value)
            )
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                f"--value for {target!r} is invalid JSON: {exc.msg}"
            ) from exc
        except ValidationError as exc:
            raise validation_error_as_bad_parameter(exc) from exc
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"--value target must be a valid rootless {target_label} path: {exc}"
            ) from exc
    return bindings


def parse_step_input_bindings_file(path: Path) -> list[InputBinding]:
    """Read and validate an ordered canonical input-binding list."""
    try:
        return _INPUT_BINDINGS_ADAPTER.validate_python(
            parse_json_file(path, option_name="--bindings-file")
        )
    except ValidationError as exc:
        raise validation_error_as_bad_parameter(exc) from exc


def parse_workflow_output_binding_flags(
    values: list[str] | None,
) -> list[InputPathBinding]:
    """Parse ordered canonical workflow-output path bindings."""
    return _parse_input_path_binding_flags(
        values,
        option_name="--map",
        target_label="workflow-output",
    )


def parse_workflow_output_value_flags(
    values: list[str] | None,
) -> list[InputValueBinding]:
    """Parse ordered canonical workflow-output literal bindings."""
    return _parse_input_value_binding_flags(values, target_label="workflow-output")


def parse_workflow_output_bindings_file(path: Path) -> list[InputBinding]:
    """Read an ordered canonical workflow-output binding list."""
    try:
        return _INPUT_BINDINGS_ADAPTER.validate_python(
            parse_json_file(path, option_name="--bindings-file")
        )
    except ValidationError as exc:
        raise validation_error_as_bad_parameter(exc) from exc


def parse_step_output_binding_flags(
    values: list[str] | None,
) -> list[OutputBinding]:
    """Parse ordered local-to-state outputs without collapsing fan-out."""
    bindings: list[OutputBinding] = []
    for item in values or []:
        source, separator, target = item.partition("=")
        if separator != "=" or not source or not target:
            raise typer.BadParameter("--map must use LOCAL_SOURCE=STATE_TARGET")
        try:
            bindings.append(
                OutputBinding(
                    source=LocalPath.parse(source),
                    target=StatePath.parse(target),
                )
            )
        except (PathResolutionError, ValidationError) as exc:
            raise typer.BadParameter(str(exc)) from exc
    return bindings


def parse_step_output_bindings_file(path: Path) -> list[OutputBinding]:
    """Read and validate an ordered canonical output-binding list."""
    try:
        return _OUTPUT_BINDINGS_ADAPTER.validate_python(
            parse_json_file(path, option_name="--bindings-file")
        )
    except ValidationError as exc:
        raise validation_error_as_bad_parameter(exc) from exc


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


def parse_json_object_file(path: Path, *, option_name: str) -> dict[str, Any]:
    """Read a JSON object file used by a workflow schema option."""
    value = parse_json_file(path, option_name=option_name)
    if not isinstance(value, dict):
        raise typer.BadParameter(f"{option_name}: expected a JSON object")
    return value


def route_source(from_step: str | None, from_outcome: str | None) -> RouteSource | None:
    if from_step is None:
        if from_outcome is not None:
            raise typer.BadParameter("--from-outcome requires --from-step")
        return None
    return RouteSource(step_id=from_step, outcome=from_outcome or "ok")
