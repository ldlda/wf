# Workflow Surface Next Actions Design

## Purpose

`next_actions` is becoming a reusable UX pattern for MCP-facing workflow tools.
It gives LLM clients a small, machine-readable answer to:

```text
What should I call next?
```

This is especially useful when a client cannot easily read resources/prompts or
when the MCP tool schema is technically correct but easy to misuse.

## Boundary

`next_actions` is guidance, not authority.

- Diagnostics describe machine-readable facts about validity, drift, source
  liveness, blocked resume, and runtime failures.
- `next_actions` explains the likely next useful tool call.
- Runtime validation, artifact validation, and dependency validation remain the
  source of truth.
- `next_actions.can_save_now` is advisory only. It must not block saving.

## Proposed Module

Create a focused module:

```text
src/wf_mcp/workflow_surface/next_actions.py
```

It should own the reusable result models and constructors. This keeps
`handlers.py` from accumulating UX policy helpers and keeps `models.py` focused
on MCP request/response schemas.

## Core Types

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field


class NextActionTool(StrEnum):
    """Stable MCP workflow tools that guidance may recommend."""

    PATCH_DRAFT_WORKSPACE = "wf.workflow.patch_draft_workspace"
    VALIDATE_DRAFT_WORKSPACE = "wf.workflow.validate_draft_workspace"
    VALIDATE_DEPLOYMENT = "wf.workflow.validate_deployment"
    RUN_DEPLOYMENT = "wf.workflow.run_deployment"
    RESUME_RUN = "wf.workflow.resume_run"
    READ_RUN_TRACE = "wf.workflow.read_run_trace"


class NextActionPatchExample(BaseModel):
    """Concrete example request for the recommended tool."""

    description: str
    tool: NextActionTool
    request: dict[str, Any]


class NextActions(BaseModel):
    """Advisory continuation hints for MCP workflow clients."""

    can_continue: bool = Field(
        description=(
            "Whether there is an obvious next workflow-surface tool call. "
            "Advisory only."
        )
    )
    can_save_now: bool | None = Field(
        default=None,
        description=(
            "Advisory wrapper-authoring signal. False means review is "
            "recommended before saving; the server does not enforce it."
        ),
    )
    recommended_next_tool: NextActionTool | None = Field(
        default=None,
        description="Suggested next MCP workflow tool, if one is obvious.",
    )
    reason: str
    patch_examples: list[NextActionPatchExample] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

## Constructors

Prefer named constructors or classmethods over ad-hoc dict helpers.

Initial constructor:

```python
@classmethod
def from_wrapper_hints(
    cls,
    *,
    workspace_id: str,
    revision: int,
    hints: WrapperAuthoringHints | dict[str, Any],
) -> Self:
    """Create guidance after create_draft_workspace_from_capability."""
```

Later constructors:

```python
@classmethod
def from_deployment_validation(
    cls,
    *,
    deployment_id: str,
    diagnostics: list[DependencyDiagnostic],
) -> Self:
    """Create guidance after validate_deployment."""


@classmethod
def from_run_result(
    cls,
    *,
    run_id: str | None,
    status: str,
    trace_count: int,
    diagnostics: list[DependencyDiagnostic],
) -> Self:
    """Create guidance after run_deployment, inspect_run, or resume_run."""
```

## Wrapper Draft Guidance Rules

For `create_draft_workspace_from_capability`:

- High confidence and no missing decisions:
  - `can_continue=true`
  - `can_save_now=true`
  - `recommended_next_tool=wf.workflow.validate_draft_workspace`
- Low/medium confidence or any missing decisions:
  - `can_continue=true`
  - `can_save_now=false`
  - `recommended_next_tool=wf.workflow.patch_draft_workspace`
  - include conservative `patch_examples` when the missing decision can be
    represented safely

Patch examples must not invent business semantics.

Allowed examples:

- replace step output bindings with an empty list as a scaffold
- point the caller to `patch_draft_workspace` with the correct `workspace_id`
  and `revision`
- include an empty patch for boolean-outcome decisions when no safe automatic
  route exists

Not allowed:

- auto-extract `content[0].text`
- auto-route on boolean output fields
- infer error outcome mapping from arbitrary output data

## Future Deployment Guidance

For `validate_deployment`:

- No diagnostics:
  - recommend `wf.workflow.run_deployment`
- `source_unreachable`:
  - recommend fixing/reloading source, then `wf.workflow.validate_deployment`
    with `live_check=true`
- `binding_missing`:
  - recommend `wf.workflow.save_deployment`
- `capability_missing` or `schema_changed`:
  - recommend inspecting capabilities or refreshing catalog before running

The exact deployment constructor can come later. The important rule is that
diagnostics stay the source of truth; `next_actions` only summarizes.

## Future Run Guidance

For `run_deployment`, `inspect_run`, and `resume_run`:

- `status=completed`:
  - no required next tool
  - optionally suggest `read_run_trace` only if caller is debugging
- `status=failed`:
  - recommend `inspect_run` or bounded `read_run_trace`
- `status=interrupted`:
  - recommend `wf.workflow.resume_run`
- blocked resume:
  - recommend repairing diagnostics and retrying `resume_run`

Never recommend reading the full trace. Always point to bounded trace ranges.

## JSON Compatibility

Existing `create_draft_workspace_from_capability` output should remain stable:

```json
{
  "next_actions": {
    "can_save_now": false,
    "recommended_next_tool": "wf.workflow.patch_draft_workspace",
    "reason": "...",
    "patch_examples": [],
    "warnings": []
  }
}
```

If the generic model adds `can_continue`, it is additive. Existing clients that
only read `can_save_now`, `recommended_next_tool`, `reason`, `patch_examples`,
and `warnings` continue to work.

## Migration Plan

1. Add `next_actions.py` with generic models and `from_wrapper_hints`.
2. Re-export or import these models from `workflow_surface.models` if needed for
   FastMCP schema generation.
3. Replace handler-local `_wrapper_draft_next_actions` helpers with the model
   constructor.
4. Keep response JSON fields stable.
5. Add tests proving the old `next_actions` fields still serialize the same.
6. Later, add deployment/run constructors in separate small passes.

## Open Questions

- Should `recommended_next_tool` allow non-workflow tools such as
  `wf.admin.reload_config`, or should guidance stay workflow-surface only?
- Should patch examples grow a typed `tool_request_schema` later, or is raw JSON
  request payload enough?
- Should `can_continue=false` appear when there is no useful next tool, or should
  `recommended_next_tool=null` be enough?
