# Artifact Delete Policy

## Status

Implemented: `wf artifact delete <artifact_id> <version> --confirm` deletes
unreferenced artifact versions and rejects versions referenced by deployments.

This is the current design contract for artifact deletion. It is separate from
`wf draft delete` because artifact deletion is not only CLI plumbing.

## Current State

- Draft workspace deletion already exists in `wf_api` and can be exposed safely
  through CLI/RPC.
- Deployment deletion already exists and is stored through
  `WorkflowArtifactStore.delete_deployment`.
- Artifact deletion exists as a store/API/RPC/CLI operation for one artifact
  version at a time.
- Deployments live in the artifact store area and can reference a specific
  `(artifact_id, version)`.

This means `wf artifact delete <artifact_id> <version>` enforces store-level
policy, not just CLI confirmation.

## Required Safety Rule

Artifact deletion must not remove an artifact version while any deployment
references that artifact version.

Deletion rejects referenced artifacts with structured output like:

```json
{
  "deleted": false,
  "artifact_id": "smoke_artifact_20260609",
  "version": 1,
  "blocked_by_deployments": ["smoke_deploy_20260609"]
}
```

The exact response can be adjusted to match existing API payload style, but it
must include the blocking deployment ids.

## Non-Goals

- Do not cascade-delete deployments.
- Do not delete runs.
- Do not delete draft workspaces that created the artifact.
- Do not add soft-delete/tombstones unless a store migration spec exists.
- Do not silently ignore missing referenced deployments.

## Future Cascade Policy

If cascade deletion is added later, make it explicit and noisy:

```bash
wf artifact delete smoke_artifact_20260609 1 --cascade-deployments --confirm
```

The non-cascade path must remain the default.

## Implementation Shape

The implemented shape is store primitives first, then API, then transport, then
CLI:

1. `WorkflowArtifactStore` gains an artifact-version delete method.
2. `WorkflowArtifactStore` gains a helper to find deployments referencing
   `(artifact_id, version)`, or the delete method returns the blockers itself.
3. `wf_api` exposes `delete_artifact(artifact_id, version)` and rejects when
   blockers exist.
4. JSON-RPC and `RpcWorkflowApiClient` expose the same operation.
5. CLI adds `wf artifact delete <artifact_id> <version> --confirm`.

## Test Requirements

Artifact deletion should keep tests for:

- Deleting an unreferenced artifact version succeeds.
- Deleting a missing artifact version is idempotent only if the existing artifact
  store style already treats deletes that way; otherwise it should return a
  clear not-found error.
- Deleting an artifact version referenced by one deployment is blocked and
  returns that deployment id.
- Deleting an artifact version referenced by multiple deployments returns all
  blocking deployment ids.
- Deleting one artifact version does not delete other versions of the same
  artifact id.
- CLI requires `--confirm`.

## Relationship To Deployment Delete

`wf deploy delete <deployment_id>` removes a deployment record. It does not remove
the artifact that deployment referenced.

`wf artifact delete <artifact_id> <version>` removes an artifact version only
after proving no deployment references it.
