# Concurrent Foreach Phase 4 Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split concurrent foreach execution into safe, independently testable runtime slices.

**Architecture:** `foreach(mode="concurrent")` is the workflow mode. Sync runtime should interleave admitted item frames one node call at a time; async runtime may later run admitted async node handlers simultaneously. All item writes must flow through `StatePatch` and commit at a foreach barrier, not directly from child frames into shared state.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2, pytest, `wf_core.runtime.scheduler`, `wf_core.runtime.foreach_state`, `wf_core.runtime.ops.state`.

---

## Current State

Already implemented:

- `ForeachNode.mode` accepts canonical `"concurrent"`.
- `ForeachConcurrentPolicy` exists with `max_active`, `max_outstanding`, and `interrupt="quiesce"`.
- Legacy `mode="parallel"` / `parallel={...}` parse into canonical concurrent shape.
- `ForeachItemErrorPolicy` exists with `fail`, `skip`, and `collect`.
- `completed_with_errors` is derived for `skip` and `collect`.
- `collect_to` is validated as a declared array state field.
- `StatePatch`, `build_output_patch(...)`, and `commit_state_patch(...)` exist.
- `ForeachBarrierState`, `PendingItemResult`, and `ItemErrorRecord` exist.
- Serial foreach progress now uses `ForeachBarrierState`.
- Sync `foreach(mode="concurrent")` runs with fail-only item policy, bounded
  admission, deterministic interleaving, item-local overlays, and barrier
  commits.
- Multi-step concurrent item bodies are supported for fail-only item policy.
- Barrier write validation rejects ambiguous sibling writes: same-path sibling
  writes require a `mergeable` reducer, and ancestor/descendant
  sibling writes are rejected.
- Concurrent `item_error.action="skip"` and `"collect"` are supported.
- `collect` writes ordered item error records to `collect_to`, writes an empty
  list on clean success, and emits `completed_with_errors` only when failures
  were collected.

## Non-Goals For Phase 4

- Do not implement Fork/Gather graph nodes.
- Do not turn `JoinNode` into a real barrier.
- Do not run sync node handlers in threads or processes.
- Do not add OpenTelemetry.
- Do not add platform-level source/tool semaphores.
- Do not add persistent run storage.

## Slice 1: Sync Concurrent Foreach, Fail-Only

Implement first because it proves the scheduler and frame admission model without async task orchestration or handled item failures.

Scope:

- `foreach(mode="concurrent", item_error.action="fail")` runs in sync runtime.
- Parent foreach admits up to `concurrent.max_active` item frames.
- Scheduler interleaves item frames one step at a time.
- Child output writes are buffered as per-item `StatePatch` objects.
- Barrier commits all successful item patches only when every item succeeds.
- Any item runtime failure fails the whole run.
- `skip` and `collect` remain runtime-unsupported for concurrent mode.

Plan:

- See [`2026-05-22-concurrent-foreach-v1-sync-fail-only.md`](2026-05-22-concurrent-foreach-v1-sync-fail-only.md).

## Slice 2: Item-Local Overlays

Implemented after Slice 1 because fail-only concurrent foreach needed
lineage-local reads before multi-step item bodies could be supported. Overlays
let later nodes in one item read earlier buffered writes from the same item
without exposing those writes to siblings.

Scope:

- `state_view_for_frame(...)` returns committed parent state plus current item
  overlay for concurrent foreach item frames.
- Parent `RunState.state` remains unchanged until the barrier commits.
- Item patches accumulate across multiple nodes in the same item lineage.
- Multi-step concurrent item bodies are supported.
- Sibling item overlays remain isolated.
- Sibling write conflict policy remains deferred to Slice 3.

Plan:

- See [`2026-05-22-concurrent-foreach-item-overlays.md`](2026-05-22-concurrent-foreach-item-overlays.md).

## Slice 3: Barrier Commit Conflict Semantics

Implement after Slice 2 so conflict checks operate on real item-local overlays
and multi-step item patches.

Scope:

- Detect sibling lineage writes to the same state path.
- If exactly one lineage writes a destination path, default replace is allowed.
- If multiple sibling lineages write the same destination path, a declared
  `mergeable` reducer is required.
- Ancestor/descendant writes across sibling lineages are conflicts unless an explicit future merge strategy covers them.
- Commit order is item index order, never completion order.

Files likely touched:

- `src/wf_core/runtime/foreach_state.py`
- `src/wf_core/runtime/ops/state.py`
- `src/wf_core/runtime/ops/foreach.py`
- `tests/core/test_concurrent_foreach.py`

Key tests:

- `test_concurrent_foreach_rejects_sibling_writes_without_reducer`
- `test_concurrent_foreach_applies_reducer_in_item_index_order`
- `test_concurrent_foreach_rejects_ancestor_descendant_write_conflict`

Plan:

- See [`2026-05-22-concurrent-foreach-barrier-write-semantics.md`](2026-05-22-concurrent-foreach-barrier-write-semantics.md).

## Slice 4: Item Error Policies

Implemented after barrier success commits became correct.

Scope:

- `item_error.action="skip"` continues after item runtime failures.
- `item_error.action="collect"` continues and writes structured errors to `collect_to`.
- Both emit `completed_with_errors` if at least one item failed.
- `collect` writes an empty list and emits `done` if all items succeed.
- Failed item frames remain `FAILED`; parent foreach decides whether the failure is handled.

Files likely touched:

- `src/wf_core/runtime/foreach_state.py`
- `src/wf_core/runtime/ops/foreach.py`
- `tests/core/test_concurrent_foreach_errors.py`

Key tests:

- `test_concurrent_foreach_skip_emits_completed_with_errors`
- `test_concurrent_foreach_collect_writes_ordered_error_records`
- `test_concurrent_foreach_collect_writes_empty_list_on_clean_success`

## Slice 5: Async Concurrent Foreach

Implement only after sync semantics are stable.

Scope:

- Async runtime may have multiple async node handler calls in flight.
- `concurrent.max_active` caps admitted/running item work.
- Sync handlers are still called normally; no thread/process executor.
- Trace remains append-only chronological execution history.
- Barrier commit order remains item index order.

Files likely touched:

- `src/wf_core/runtime/engine.py`
- `src/wf_core/runtime/step.py`
- `src/wf_core/runtime/ops/nodes.py`
- `src/wf_core/runtime/ops/foreach.py`
- `tests/core/test_concurrent_foreach_async.py`

Key tests:

- `test_async_concurrent_foreach_respects_max_active`
- `test_async_concurrent_foreach_commits_in_item_index_order`

## Slice 6: Interrupt Quiescence

Implement after async execution exists.

Scope:

- If any concurrent item interrupts, the whole run pauses.
- No new item frames are admitted after the interrupt.
- Already-started async node calls drain to pending results.
- The caller gets control only at a quiescent point.
- Pending results do not commit until resume/commit policy allows it.

Files likely touched:

- `src/wf_core/runtime/engine.py`
- `src/wf_core/runtime/preparation.py`
- `src/wf_core/runtime/ops/interrupts.py`
- `src/wf_core/runtime/ops/foreach.py`
- `tests/core/test_concurrent_foreach_interrupts.py`

Key tests:

- `test_concurrent_foreach_interrupt_returns_after_quiescence`
- `test_resume_prioritizes_interrupted_item_frame_before_siblings`

## Execution Order

1. Sync concurrent foreach, fail-only.
2. Item-local overlays for multi-step item bodies.
3. Barrier conflict semantics.
4. `skip` / `collect` item error policies.
5. Async concurrent foreach.
6. Interrupt quiescence.

## Self-Review

- Spec coverage: the roadmap covers scheduler admission, barrier commits, reducer conflicts, handled item failures, async handler execution, and interrupt quiescence.
- Placeholder scan: each slice has scope, likely files, and named tests; concrete code lives in the slice-specific plan.
- Type consistency: the roadmap uses canonical `concurrent`, `ForeachConcurrentPolicy`, `ForeachBarrierState`, `PendingItemResult`, and `StatePatch`.
