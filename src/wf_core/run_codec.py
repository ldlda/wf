from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from .run_state import ROOT_SCOPE_ID, RunState


class PersistedRunState(BaseModel):
    """Versioned JSON storage envelope for one stopped runtime snapshot."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    state: dict[str, Any]


_RUN_STATE_ADAPTER = TypeAdapter(RunState)


def dump_run_state(run: RunState) -> dict[str, object]:
    """Serialize one stopped `RunState` into the durable v1 envelope."""
    return PersistedRunState(
        state=_RUN_STATE_ADAPTER.dump_python(run, mode="json")
    ).model_dump(mode="json")


def load_run_state(payload: object) -> RunState:
    """Validate and restore one durable v1 runtime snapshot.

    The root scope intentionally shares the compatibility ``RunState.state``
    dict during runtime. Serialization loses object identity, so restored
    snapshots must recreate this alias before resumed writes occur.
    """
    envelope = PersistedRunState.model_validate(payload)
    try:
        run = _RUN_STATE_ADAPTER.validate_python(envelope.state)
    except ValidationError as exc:
        raise ValueError("invalid persisted workflow run state") from exc
    root_scope = run.scopes.get(ROOT_SCOPE_ID)
    if root_scope is not None:
        run.state = root_scope.committed_state
    return run
