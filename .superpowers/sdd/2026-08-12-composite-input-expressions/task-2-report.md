# Task 2 Report: Resolve And Validate Expressions In Core Execution

## Status

Implemented and verified. Core runtime input resolution now supports the
canonical composite input expressions from Task 1 across node execution,
prepared subgraph boundaries, and interrupt requests. Structural validation
walks every nested path expression while keeping each top-level binding
atomic for target-overlap checks.

## Changed Content

- Added `src/wf_core/runtime/input_bindings.py` with:
  - `resolve_input_expression()` for literal, path, array, and object nodes;
  - `resolve_step_input_bindings()` for simple and composite bindings;
  - strict JSON validation for values read from graph sources;
  - location-preserving `WorkflowExecutionError` messages for missing paths and
    local-target failures.
- Replaced duplicated input-binding loops in:
  - `src/wf_core/runtime/ops/nodes.py`;
  - `src/wf_core/runtime/subgraphs.py`;
  - `src/wf_core/runtime/ops/interrupts.py`.
- Extended `src/wf_core/validation/steps.py` to accept `StepInputBinding`,
  recursively validate every `PathExpression`, and report nested source paths
  such as `nodes[0].input[0].expression.fields.name.path`.
- Added runtime and validation coverage in:
  - `tests/core/test_input_expression_runtime.py`;
  - `tests/core/test_mapping_validation.py`.

## TDD Evidence

- RED: the new focused suite initially failed during collection because the
  shared runtime resolver module did not exist.
- GREEN: after implementation, the focused suite passed and was extended with
  explicit input/context path, nested location, and local-target failure cases.

## Verification

- Focused Task 2 suites: `35 passed`.
- Full core suite: `285 passed`.
- Ruff check: clean for all changed source and test files.
- Ruff format check: all changed files already formatted.
- Scoped basedpyright: `0 errors, 0 warnings, 0 notes` for
  `src/wf_core/runtime` and `src/wf_core/validation`.
- `git diff --check`: clean apart from normal Windows line-ending warnings.

## Concerns

- The Python authoring builder and artifact adapter still carry the separate
  Task 1 follow-up for widening `InputBindingArg`; this task intentionally
  consumes the canonical models at the core runtime boundary and does not
  redesign that authoring API.
- Workflow-level `project_output` remains on the simple path/value union as
  required by the brief.
