# Issues

## Draft authoring parity

- [ ] No dedicated draft CLI subcommands for adding non-capability step kinds.
- [ ] `DraftInterruptPayload` cannot preserve `request_schema` or
  `resume_schema`, so typed interrupt contracts cannot be authored through the
  draft model.
- [ ] `DraftStep` and its adapter have no subgraph representation even though
  `SubgraphNode` is a canonical core step.
