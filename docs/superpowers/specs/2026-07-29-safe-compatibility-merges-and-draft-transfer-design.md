# Safe Compatibility Merges And Draft Transfer Design

## Status

Approved for implementation planning on 2026-07-29.

## Problem

Draft step inputs and outputs are stored as ordered canonical binding lists.
Those lists support repeated sources, literal values, and ordering that the
older compatibility maps cannot represent. A later compatibility-map merge can
therefore read valid canonical bindings into dictionaries and silently rewrite
them into a different list.

Draft workspaces also lack a direct CLI workflow for moving a complete draft
document between tools or restoring an edited snapshot. Operators can extract a
draft from `inspect`, but there is no revision-checked import operation, file
overwrite policy, or local/remote parity.

## Goals

- Prevent compatibility-map merges from silently changing canonical bindings
  they cannot represent.
- Reject unsafe merges before mutation and direct callers to canonical binding
  replacement.
- Preserve compatibility merges for drafts that are exactly representable.
- Export the exact stored draft document to a JSON file.
- Import a complete draft into an existing workspace under revision control.
- Recompute semantic validation for imported documents.
- Give local and remote CLI targets identical behavior.

## Non-Goals

- Removing the compatibility map operations.
- Inventing syntax for selecting one binding from an ambiguous fan-out group.
- Making maps capable of representing canonical binding lists.
- Creating, renaming, or cloning workspaces during import.
- Exporting workspace revision, timestamps, status, or diagnostics.
- Adding TypeScript JSON-RPC coverage or generating transport contracts.
- Adding a generic backup archive containing artifacts, deployments, or runs.

## Compatibility Merge Policy

Compatibility merges remain available only when the operation can preserve the
existing canonical list exactly, except for the entries explicitly updated or
appended by the requested map.

An unsafe merge returns an input error before any patch or revision increment.
The error identifies the selected step or workflow output and tells the caller
to inspect the canonical list, edit it explicitly, and replace it through the
corresponding canonical binding operation.

### Step Inputs

Step-input compatibility maps use graph source paths as dictionary keys and
keep literal values in a separate target-keyed dictionary. The API checks that
the existing ordered input list survives conversion to those maps and back
without changing:

- binding count;
- binding order;
- source and target paths;
- literal values;
- path/literal interleaving.

This rejects source fan-out, duplicate literal targets, and any ordering that
the map serializer would rearrange. A simple list with unique path sources and
an exactly reproducible literal suffix remains mergeable.

### Step Outputs

Step-output compatibility maps use local source paths as dictionary keys. The
API checks that the existing output list survives map conversion and
serialization exactly. Repeated local sources therefore reject compatibility
merge because the request cannot identify which fan-out binding should change.

### Workflow Outputs

The current workflow-output merge implementation already preserves unrelated
ordered bindings and literals without rebuilding the complete list through a
dictionary. It remains safe when each requested source identifies at most one
existing path binding.

If a requested source occurs more than once, the merge is ambiguous and is
rejected rather than updating every fan-out target. Duplicate sources that are
not mentioned by the requested map remain unchanged.

### Error Guidance

Representative messages are:

```text
step 'render' inputs cannot be safely merged through a compatibility map;
replace the complete canonical binding list instead
```

```text
workflow output source 'state.title' has multiple bindings and cannot be
updated through a compatibility map; replace the complete canonical binding
list instead
```

CLI help continues to label `--merge` as compatibility-only, but no longer
describes it as silently or acceptably lossy.

## Draft Export

Add:

```text
wf draft export WORKSPACE --output PATH [--force]
```

The command requests the workspace with `include_draft=True` and writes only
the `draft` object as formatted UTF-8 JSON with a final newline.

- `--output` is required.
- An existing path is rejected unless `--force` is supplied.
- Parent directories must already exist.
- File errors are reported as CLI input errors.
- The command does not print a second JSON representation to stdout.
- Export does not mutate the workspace.

The exported document intentionally excludes workspace metadata. Revision is a
property of the destination workspace and must be supplied explicitly during
import.

## Draft Import

Add:

```text
wf draft import WORKSPACE --revision N --file PATH
```

Import replaces the draft document in an existing workspace. It does not create
a workspace when the ID is missing and does not take a workspace ID from the
file.

The operation performs these steps:

1. Parse the file as a JSON object.
2. Validate the request envelope.
3. Check the expected workspace revision.
4. Structurally validate the complete document as `WorkflowDraft`.
5. Resolve current capability definitions and semantically validate the whole
   draft.
6. Persist the document and its fresh status and diagnostics in one
   revision-checked store replacement.

A structurally malformed document, stale revision, missing workspace, or store
conflict leaves the workspace unchanged. A structurally valid but semantically
invalid draft is persisted with fresh diagnostics so it can be inspected and
repaired through the normal draft-authoring workflow.

Importing a document identical to the stored draft is an exact no-op and does
not increment the revision. Revalidation without replacement remains the
responsibility of `wf draft validate`.

## Full-Document Replacement Boundary

The existing `replace_validated_draft_document` helper must not power import.
That helper is intentionally limited to focused edits whose fields have already
been validated and cannot change capability contracts; it preserves the
workspace's current semantic status and diagnostics.

Add a distinct full-document replacement operation in the draft workspace/API
layer. Its name and docstring must make semantic revalidation explicit. The
operation reuses the existing `WorkflowDraft` model, capability-definition
resolution, draft validation, summary, conflict, and store replacement helpers.
It must not add another workflow validator.

## Transport Design

Export needs no new server operation because the existing inspect operation can
return the full draft.

Import adds one Python JSON-RPC operation and matching remote client handler for
full-document replacement. The CLI calls the same handler method for local and
remote targets. The request carries:

```json
{
  "workspace_id": "report",
  "revision": 4,
  "draft": {}
}
```

The draft field uses the existing raw draft/document model boundary. Transport
validation must reject non-object values before semantic authoring logic runs.
This slice does not add the operation to the TypeScript RPC package.

## Testing

### Compatibility Merges

Add focused API tests for:

- representable step-input merge;
- step-input source fan-out rejection;
- step-input literal/interleaving rejection;
- representable step-output merge;
- step-output source fan-out rejection;
- workflow-output merge preserving unrelated fan-out and literals;
- workflow-output rejection when the requested source is ambiguous;
- stale revision precedence where required by the existing API contract;
- unchanged draft and revision after every rejected merge.

Add CLI tests proving `--merge` still selects the compatibility handlers and
that remote errors present the canonical-replacement guidance.

### Draft Transfer

Add tests for:

- exact export document shape and formatted JSON;
- overwrite refusal and `--force`;
- missing parent and file-write failures;
- local export and remote export through full inspection;
- successful import with a revision increment;
- identical import as a no-op;
- stale revision conflict;
- malformed JSON and non-object input;
- structurally invalid draft without mutation;
- semantically invalid draft persisted with fresh diagnostics;
- current capability definitions used during import validation;
- local and remote CLI dispatch parity;
- JSON-RPC request and response behavior.

Round-trip one exported document into a different existing workspace and assert
that its stored draft equals the exported object. Workspace IDs and revisions
remain destination metadata and are not copied.

## Documentation And Issue State

After verification:

- mark the compatibility-map fan-out issue complete in `ISSUES.md`;
- document that compatibility merge now rejects unrepresentable canonical
  lists;
- add export/import examples to CLI-facing documentation and `skills/wf-cli`;
- add a completed roadmap entry linked to the archived implementation plan;
- archive the implementation plan under
  `docs/historical/superpowers/plans/`.

## Success Criteria

- No compatibility-map merge can silently collapse or ambiguously rewrite
  canonical fan-out.
- Simple representable map merges remain operational.
- Rejected merges are atomic and explain how to use canonical replacement.
- A draft document can be exported and imported through local or remote CLI.
- Import is revision checked and recomputes semantic status and diagnostics.
- Export/import do not leak or overwrite workspace metadata.
- No second binding model, workflow validator, or TypeScript transport contract
  is introduced.
- Focused tests, Ruff, formatting, and basedpyright pass.
