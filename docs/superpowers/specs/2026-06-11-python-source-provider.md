# Python Source Provider

Date: 2026-06-11

Status: planned first non-MCP source family

Related:

- [Runtime source lifecycle](./2026-06-09-runtime-source-lifecycle.md)
- [Workflow config targets and sources](./2026-06-03-workflow-config-targets-and-sources.md)
- [Long-lived workflow API boundary](./2026-06-03-long-lived-workflow-api-boundary.md)
- [Project map](../../project_map.md)

## Purpose

`wf_sources_python` should prove that workflow sources are not MCP-shaped. It is
not a replacement for `wf_authoring`; it is the provider package that loads
project-local Python capabilities and projects them into `WorkflowApi` as
ordinary `CapabilitySource` and executable `NodeSpec` objects.

## Boundary

```text
wf_authoring
  owns authoring primitives:
    @node
    NodeSpec
    build_registry / build_async_registry
    reducers
    WorkflowBuilder

wf_sources_python
  owns source-provider glue:
    config entry interpretation
    module/object loading
    validation of exported specs
    source qualification
    CapabilitySource projection

wf_server
  owns composition:
    read wf_config
    select provider by source kind
    merge provider sources with built-ins
```

So `wf_sources_python` acts more like `wf_sources_mcp` than `wf_authoring`.
`wf_authoring` creates specs; `wf_sources_python` imports and exposes specs from
user code.

## First Slice

Start with static config only:

```json
{
  "kind": "python",
  "id": "local.ops",
  "module": "my_project.workflow_ops",
  "registry": "registry"
}
```

The loaded object may be:

- a mapping of local name to `NodeSpec`
- a sequence of `NodeSpec`
- a callable returning either of the above

The provider qualifies local specs under the configured source id. A local spec
named `echo` becomes `local.ops.echo`. A spec already named
`authoring.echo` should become `local.ops.echo`, matching built-in source
qualification behavior.

## Non-Goals For First Slice

- No source registry mutation/apply support.
- No hot reload on every call.
- No subprocess sandbox.
- No package installation or dependency management.
- No move of `wf.std` or `wf.recipes`.
- No reducer loading until a concrete use case needs it.
- No OpenAPI/HTTP source behavior.

## Error Policy

Configuration and import errors should fail server construction clearly:

- module cannot be imported
- registry object is missing
- registry object is not a supported shape
- exported value is not a `NodeSpec`
- duplicate local spec names inside one Python source

Runtime errors from Python node execution are ordinary workflow node failures,
not source-load failures.

## Why Not Move `wf.recipes`

`wf.recipes` is first-party built-in workflow content. It belongs with local
sources because it is always available and versioned with the platform.

`wf_sources_python` is for user/project-defined source entries configured by a
server operator. It should be optional and explicit.

## Later Slices

After static config works:

1. Add source registry/apply support for Python source entries.
2. Consider explicit development reload.
3. Consider reducer exports if a real project source needs custom reducers.
4. Consider isolation policy for untrusted Python. The first version is trusted
   in-process code only.

