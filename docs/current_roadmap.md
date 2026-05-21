# Current Roadmap

This is the short active roadmap after the core type-shape cleanup. It is based
on both the current docs and the implementation state.

## Next Work

1. **Docs index and prune**
   - Add/maintain a clear docs entry point.
   - Keep current architecture docs separate from historical plans and scratch
     notes.

2. **MCP workflow authoring UX**
   - Make the LLM/client path progressive: inspect sources, create a draft,
     patch, validate, compile, save, run.
   - Prefer smaller discovery/inspection responses over one huge payload.

3. **Wrapper creation ergonomics**
   - Help create workflow-ready wrappers from raw capabilities.
   - Suggest state schema, input bindings, output bindings, default `ok` /
     `error` handling, and missing decisions.

4. **Run and deployment story**
   - Tighten list/inspect/run/debug for artifacts and deployments.
   - Keep dependency validation and trace/error output compact and actionable.

5. **Source inventory polish**
   - Make `list_sources` / `inspect_source` clearly show raw capabilities,
     workflow-ready node specs, admin-only tools, docs/resources, enabled state,
     and changes after reload.

## Runtime Work To Revisit Later

- **Native subgraphs**: add child run state, child trace preservation, interrupt
  bubbling, and resume back into the child workflow.
- **Async parallel foreach**: add explicit scheduling, reducer/merge semantics,
  and failure policy. Do not model this as plain parallel calls over sync
  handlers.

## Why This Order

`wf_core` is now coherent enough for the next bottleneck to be platform and DX:
how a human or LLM discovers capabilities, turns them into workflow-ready
pieces, saves them, and runs them again.
