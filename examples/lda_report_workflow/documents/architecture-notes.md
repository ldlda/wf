# Architecture Notes

Lifecycle:

- Drafts are mutable authoring workspaces with revisions.
- Artifacts are immutable versioned workflow definitions.
- Deployments bind logical source ids to configured concrete sources.
- Runs persist stopped execution records and bounded traces.

Runtime:

- The core executes typed graph nodes and routes by declared outcomes.
- State writes go through reducer-aware merge semantics.
- Interrupt nodes pause at explicit human-in-the-loop boundaries.
- Resume payloads are validated before state mutation.

Source providers:

- Python sources support trusted local demo capabilities.
- MCP sources preserve upstream session state through a runtime pool.
- OpenAPI source support exists as an experimental provider.
