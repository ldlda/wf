"""Executor-only operations used by `wf_core.runtime`.

This package owns the runtime implementation helpers: node execution, state
writes, frame movement, foreach, interrupts, indexes, and schema checks.
Callers should use `wf_core.runtime` unless they are extending the executor.
"""
