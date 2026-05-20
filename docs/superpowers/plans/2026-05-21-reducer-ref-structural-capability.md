# ReducerRef Structural Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reducer references from ambiguous dotted strings toward structural capability refs while preserving string reducer names as parse-only shorthand.

**Architecture:** Reducers are source-owned capabilities, not graph paths. `ReducerRef` should carry a structural `CapabilityRef` plus config, while old `name` strings continue to validate at compatibility boundaries. Artifact dependency extraction should use the structural ref instead of reparsing dotted reducer names.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_platform.refs.CapabilityRef`, `wf_core.models.reducers.ReducerRef`, `wf_artifacts.factory`, pytest, basedpyright, ruff.

---

## Planned Shape

Current compatibility shape:

```json
{"name": "wf.std.add", "config": {}}
```

Future canonical shape:

```json
{
  "ref": {"source": "wf.std", "capability_key": "add"},
  "config": {}
}
```

String shorthand should continue to parse:

```json
"wf.std.add"
```

or:

```json
{"name": "wf.std.add", "config": {"modulus": 10}}
```

but saved model dumps should prefer `ref`.

## Scope Notes

- Do not treat reducer refs as `StatePath`.
- Do not split reducer names using graph-path helpers.
- Keep reducer config as part of `ReducerRef`; config does not affect the dependency key.
- Update artifact dependency extraction to read `ReducerRef.ref`.
- Keep runtime reducer lookup compatible with existing reducer registries keyed by display name until reducer catalogs are source-keyed.

## First Implementation Tasks

1. Add tests for `ReducerRef.model_validate("wf.std.add")`.
2. Add tests for canonical `{"ref": {"source": "wf.std", "capability_key": "add"}}`.
3. Add a display-name compatibility property if runtime registries still use string keys.
4. Update `_required_reducers_from_plan()` to use structural refs.
5. Update docs and inventory output only after the model is stable.
