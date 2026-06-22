# `wf schema` Command Design

## Status

Approved design for implementation planning.

## Purpose

`wf schema` gives human and machine clients a public discovery surface for the
workflow document models accepted by the product. It should cover draft, raw
plan, core workflow, and referenced component shapes without requiring agents
to inspect tests or implementation code.

The command has two output levels:

- a compact machine-readable outline by default;
- a complete valid JSON Schema document with `--verbose`.

## Goals

1. Cover every schema definition reachable from workflow draft, raw plan, and
   core workflow roots.
2. Keep default output compact enough for agent context windows.
3. Keep all output valid JSON.
4. Make verbose output a valid, self-contained JSON Schema document.
5. Provide discoverable aliases for the common root models.
6. Fail clearly and nonzero for unknown schema names.
7. Avoid adding runtime dependencies for trivial in-process caching.

## Non-Goals

- Building a general-purpose JSON Schema browser.
- Searching arbitrary source-code models outside the workflow document domain.
- Producing Python source declarations or generated Pydantic models.
- Replacing command-specific help, validation diagnostics, or workflow docs.
- Guaranteeing that compact outlines preserve every JSON Schema keyword.

## Command Surface

```text
wf schema
wf schema list
wf schema draft
wf schema raw
wf schema core
wf schema WorkflowDraft
wf schema RawWorkflowPlan
wf schema NodeUse
wf schema InputPathBinding
wf schema raw --verbose
wf schema NodeUse --verbose
```

`wf schema` with no argument is equivalent to `wf schema list`.

The command remains a single Typer command with an optional positional name.
`draft`, `raw`, and `core` are aliases, not subcommands.

## Root Models And Aliases

| Alias | Canonical model | Purpose |
| --- | --- | --- |
| `draft` | `WorkflowDraft` | Patch-friendly draft workspace document |
| `raw` | `RawWorkflowPlan` | Raw graph accepted by artifact creation |
| `core` | `Workflow` | Canonical core workflow graph |

Canonical names are also accepted directly. Definitions exposed through the
combined root schemas are queryable by their exact canonical names.

## Schema Catalog

The implementation builds one cached catalog from:

- `TypeAdapter(WorkflowDraft).json_schema()`;
- `TypeAdapter(RawWorkflowPlan).json_schema()`;
- `TypeAdapter(Workflow).json_schema()`.

The catalog records:

- canonical root schemas;
- aliases;
- every reachable `$defs` entry;
- description/title metadata;
- which roots reference each definition.

Use `functools.cache` for catalog construction. The CLI process is short-lived;
a TTL cache and the `cachetools` dependency provide no useful behavior.

Pydantic's `TypeAdapter.json_schema()` remains the authority for schema
generation. Do not reimplement model-to-JSON-Schema conversion, discriminated
unions, aliases, defaults, validation constraints, or reference construction.
Use the existing `jsonschema` package to validate emitted full schemas. Custom
code is limited to catalog indexing, collision checks, and the explicitly
non-validating compact presentation layer.

If two roots expose different definitions with the same canonical name, catalog
construction must fail with a clear internal error rather than silently choose
one. Structurally identical definitions may be deduplicated.

## List Output

`wf schema` and `wf schema list` emit JSON:

```json
{
  "schemas": [
    {
      "name": "WorkflowDraft",
      "aliases": ["draft"],
      "kind": "root",
      "description": "Patch-friendly JSON authoring document."
    },
    {
      "name": "NodeUse",
      "aliases": [],
      "kind": "definition",
      "description": "Concrete use of a reusable node definition."
    }
  ]
}
```

Entries are sorted by canonical name. Search/filtering is deferred until real
catalog size or usage demonstrates a need.

## Compact Outline Output

The default named-schema output is a JSON **schema outline**, not a JSON Schema
document. It must label itself accordingly and must not emit dangling `$ref`
values.

Example:

```json
{
  "name": "RawWorkflowPlan",
  "kind": "schema_outline",
  "type": "object",
  "description": "Raw authoring plan using core graph models.",
  "required": [
    "name",
    "input_schema",
    "state_schema",
    "output_schema",
    "start",
    "nodes",
    "edges"
  ],
  "properties": {
    "name": {"type": "string"},
    "start": {"type": "string"},
    "nodes": {
      "type": "array",
      "items": {
        "one_of": [
          "NodeUse",
          "SubgraphNode",
          "ConditionNode",
          "ForeachNode",
          "JoinNode",
          "EndNode",
          "InterruptNode"
        ]
      }
    },
    "edges": {"type": "array", "items": "Edge"}
  },
  "related": ["Edge", "NodeUse", "OutputBinding"],
  "full_schema_command": "wf schema raw --verbose"
}
```

### Outline Projection Rules

- Preserve `name`, `title`, `description`, object `required`, defaults, enums,
  constants, and basic validation bounds when present.
- Preserve object property names.
- Convert local `$ref` values to canonical definition-name strings.
- Convert `oneOf`/`anyOf` reference unions to `one_of` name lists when all
  branches are named references.
- Preserve simple inline primitive unions in compact JSON form.
- For arrays, summarize the item schema recursively.
- Add a sorted `related` list containing definitions referenced by the outline.
- Do not recursively inline referenced definitions; callers can query them by
  name.
- Do not claim the outline is directly accepted as a validation schema.

The projection should be deterministic so snapshots and prompt provenance are
stable across runs when source models do not change.

## Verbose JSON Schema Output

`wf schema <name> --verbose` emits a complete, self-contained JSON Schema
document through the existing `wf_cli.io.emit_json` helper.

For root aliases/canonical root names, emit the complete Pydantic-generated root
schema with its `$defs` table.

For a component definition such as `NodeUse`, emit a valid root document:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/NodeUse",
  "$defs": {
    "NodeUse": {},
    "InputPathBinding": {},
    "InputValueBinding": {},
    "OutputBinding": {}
  }
}
```

The `$defs` table contains the full combined Pydantic-generated definition
catalog. Do not hand-roll transitive reference pruning or JSON Schema reference
resolution in the first implementation. The larger verbose payload is an
acceptable tradeoff for correctness; `--verbose` is explicitly the unbounded
form.

All verbose documents must pass `Draft202012Validator.check_schema()` and a
validator-backed local-reference resolution test.

## Output And Errors

- Use `emit_json`; never pass dictionaries directly to `typer.echo`.
- Unknown names raise `typer.BadParameter` and exit nonzero.
- Unknown-name messages include close canonical/alias matches when available,
  using the standard library `difflib.get_close_matches`.
- Missing names list the catalog rather than showing an empty command group.
- Internal catalog collisions or malformed generated schemas fail loudly with
  actionable errors.
- `--verbose` applies to both aliases and canonical names.

Example error:

```text
Invalid value: unknown schema 'Node'. Did you mean 'NodeUse'?
```

## Help Text

Help must describe the real single-command shape:

```text
Usage: wf schema [OPTIONS] [NAME]

Print a compact workflow schema outline, or a full JSON Schema with --verbose.
Use `wf schema` or `wf schema list` to discover available names.
Common aliases: draft, raw, core.
```

Do not call aliases convenience subcommands.

## Skills And Documentation

Update user-facing agent instructions so they use public discovery surfaces in
this order:

1. `wf schema` to list available workflow document shapes;
2. `wf schema draft` or `wf schema raw` for compact guidance;
3. `wf schema <definition>` for component details;
4. `--verbose` only when a complete validation schema is necessary;
5. workflow validation commands to check an authored document.

Remove the stale statement that `wf schema` is an empty WIP group. Keep test and
implementation file paths out of user-facing skills.

## Tests

Focused CLI tests must cover:

- `wf schema` and `wf schema list` return the same sorted catalog;
- catalog output is valid JSON and includes roots, aliases, and components;
- aliases and canonical root names resolve to the same model;
- compact output is valid JSON and contains no `$ref` keys;
- compact references are represented by queryable canonical names;
- verbose root output passes JSON Schema validation;
- verbose component output has no unresolved local `$ref` values;
- `--verbose` works for aliases and canonical component names;
- unknown names exit nonzero and offer a close-match suggestion;
- help text describes aliases rather than subcommands;
- the removed WIP help assertions are replaced with behavioral tests.

Run focused verification against the schema command and existing CLI app tests,
then run Ruff and basedpyright on modified files.

## Migration

The current uncommitted prototype is replaced rather than preserved:

- remove `cachetools` from runtime dependencies and the lockfile;
- remove TTL caches;
- replace `_sonset_sandstorm` with explicit catalog helpers;
- replace Python-repr output with JSON;
- replace detached `$defs` fragments with compact outlines;
- update stale CLI tests and skills.

No compatibility behavior is required because the previous `wf schema` surface
was explicitly an empty work-in-progress group and the prototype has not been
released as a documented contract.

## Acceptance Criteria

- Agents can discover all supported workflow schema names without reading code.
- Default output is compact, deterministic, valid JSON, and has no dangling
  references.
- `--verbose` output is valid, self-contained JSON Schema.
- Unknown names fail nonzero.
- No new runtime dependency is needed.
- Focused CLI tests, Ruff, and basedpyright pass.
- User-facing skills direct agents to `wf schema` instead of tests or source.
