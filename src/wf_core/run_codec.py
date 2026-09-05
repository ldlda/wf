from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from .run_state import ROOT_SCOPE_ID, RunState
from .runtime.limits import RunLimits


class PersistedRunState(BaseModel):
    """Versioned JSON storage envelope for one stopped runtime snapshot."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[2] = 2
    state: dict[str, Any]


class _AnyPersistedRunState(BaseModel):
    """Loading envelope accepting every currently readable version."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2]
    state: dict[str, Any]


_RUN_STATE_ADAPTER = TypeAdapter(RunState)


def dump_run_state(run: RunState) -> dict[str, object]:
    """Serialize one stopped `RunState` into the durable v2 envelope."""
    return PersistedRunState(
        state=_RUN_STATE_ADAPTER.dump_python(run, mode="json")
    ).model_dump(mode="json")


def _inject_v1_budget_defaults(state: dict[str, Any]) -> dict[str, Any]:
    """Copy a v1 state dict with the one-time step budget defaults applied.

    Version-1 envelopes predate step budgets, so they receive the default
    limit, a zeroed counter, and an unassigned number per frame exactly once
    at load time. Pre-budget trace entries and any outstanding interrupt keep
    an unassigned (``None``) number: attempts made before the upgrade are
    outside the new budget.
    """
    upgraded = deepcopy(state)
    upgraded.setdefault("limits", {"max_steps": RunLimits().max_steps})
    upgraded.setdefault("steps_executed", 0)
    frames = upgraded.get("frames")
    if isinstance(frames, dict):
        for frame in frames.values():
            if isinstance(frame, dict):
                frame.setdefault("step_number", None)
    trace = upgraded.get("trace")
    if isinstance(trace, list):
        for entry in trace:
            if isinstance(entry, dict):
                entry.setdefault("step_number", None)
    interrupt = upgraded.get("interrupt")
    if isinstance(interrupt, dict):
        interrupt.setdefault("step_number", None)
    return upgraded


def _require_v2_budget_fields(state: dict[str, Any]) -> None:
    """Reject v2 payloads missing budget fields as corrupt state.

    Unlike v1, a v2 envelope promises budget fields; a missing counter is
    corruption, not another request for defaults. Trace and interrupt entries
    always carry the key (``None`` only for upgraded pre-budget history), so a
    missing key is likewise corrupt even though the dataclass default would
    otherwise mask it.
    """
    if "limits" not in state or "steps_executed" not in state:
        raise ValueError("invalid persisted workflow run state: missing step budget")
    frames = state.get("frames")
    if not isinstance(frames, dict):
        raise ValueError("invalid persisted workflow run state: missing frames")
    for frame_id, frame in frames.items():
        if not isinstance(frame, dict) or "step_number" not in frame:
            raise ValueError(
                "invalid persisted workflow run state: "
                f"frame {frame_id!r} is missing its step number"
            )
    trace = state.get("trace")
    if isinstance(trace, list):
        for position, entry in enumerate(trace):
            if not isinstance(entry, dict) or "step_number" not in entry:
                raise ValueError(
                    "invalid persisted workflow run state: "
                    f"trace entry {position!r} is missing its step number"
                )
    interrupt = state.get("interrupt")
    if interrupt is not None:
        if not isinstance(interrupt, dict) or "step_number" not in interrupt:
            raise ValueError(
                "invalid persisted workflow run state: "
                "interrupt is missing its step number"
            )


def _restore_root_alias(run: RunState) -> RunState:
    """Recreate the root scope compatibility alias lost by serialization."""
    root_scope = run.scopes.get(ROOT_SCOPE_ID)
    if root_scope is not None:
        run.state = root_scope.committed_state
    return run


def load_run_state_with_upgrade(payload: object) -> tuple[RunState, bool]:
    """Validate one durable snapshot, upgrading v1 envelopes exactly once.

    Returns the restored run plus whether a v1-to-v2 upgrade was applied.
    """
    envelope = _AnyPersistedRunState.model_validate(payload)
    if envelope.version == 1:
        state = _inject_v1_budget_defaults(envelope.state)
        try:
            run = _RUN_STATE_ADAPTER.validate_python(state)
        except ValidationError as exc:
            raise ValueError("invalid persisted workflow run state") from exc
        return _restore_root_alias(run), True
    _require_v2_budget_fields(envelope.state)
    try:
        run = _RUN_STATE_ADAPTER.validate_python(envelope.state)
    except ValidationError as exc:
        raise ValueError("invalid persisted workflow run state") from exc
    return _restore_root_alias(run), False


def load_run_state(payload: object) -> RunState:
    """Validate and restore one durable runtime snapshot.

    Version-1 envelopes receive step budget defaults via the one-time upgrade.
    The root scope intentionally shares the compatibility ``RunState.state``
    dict during runtime. Serialization loses object identity, so restored
    snapshots must recreate this alias before resumed writes occur.
    """
    run, _ = load_run_state_with_upgrade(payload)
    return run
