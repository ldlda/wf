# Structural Refs

Qualified names are display strings. They are not authoritative identifiers.

The platform still accepts old dotted strings at MCP/API boundaries when it can
parse them, but saved workflow artifacts and deployments should store structural
refs from now on. A dotted string may be shown to humans and LLM clients, but
runtime code should not infer source boundaries from it.

## Why

These strings look similar but mean different things:

```text
context7.default.query-docs
workflow.echo_wrapper.v1
demo.foo.bar
```

`context7.default.query-docs` usually means a concrete external source and a
capability key. `workflow.echo_wrapper.v1` means a saved workflow artifact and
artifact version. `demo.foo.bar` is ambiguous: it could be source `demo` with
capability key `foo.bar`, or source `demo.foo` with capability key `bar`.

No first-dot, last-dot, or regex parser can recover a boundary that was not
stored.

## Capability Refs

Use a source plus a local capability key:

```json
{
  "source": "demo",
  "capability_key": "foo.bar"
}
```

The `capability_key` is local to the known source. It may contain dots. Those
dots do not carry source meaning.

Old input like `"demo.foo.bar"` may still parse at compatibility boundaries, but
that parse is best-effort and should not be used for new saves.

## Workflow Artifact Refs

Saved workflow and wrapper capabilities are a separate domain:

```json
{
  "artifact_id": "echo_wrapper",
  "version": 1
}
```

The display string `workflow.echo_wrapper.v1` remains useful for lists,
inspection, and old callers, but it is not the canonical saved shape.

## Deployment Bindings

Deployment bindings map an artifact-local logical source to a concrete source:

```json
{
  "logical_source": "demo",
  "concrete_source": "demo.personal"
}
```

Neither field is a capability name. Runtime code uses this source mapping before
looking up the capability key.

## Graph Paths

Capability refs and graph paths are different domains.

Path strings such as `input.text`, `state.person.name`, and `output.echoed`
describe graph data movement. Do not reuse capability-ref parsing rules for
graph paths.

New canonical graph path JSON uses root/parts objects:

```json
{
  "root": "input",
  "parts": ["message"]
}
```

## Authoring Path Inputs

`wf_authoring` accepts ergonomic path inputs and normalizes them into the core
path objects before building canonical node bindings.

Single string arguments are TOML key expressions:

```python
state("person.name")          # state -> person -> name
state('"person.name"')        # state -> "person.name"
state('person."full name"')   # state -> person -> "full name"
```

Varargs and iterables are literal path segments:

```python
state("person.name", "email") # state -> "person.name" -> email
state(("person.name",))       # state -> "person.name"
```

Builder canonical bindings use the path kind implied by position:

```python
g.use(
    node,
    input=[
        {
            "target": {"root": "local", "parts": ["payload.email"]},
            "path": {"root": "input", "parts": ["email.address"]},
        }
    ],
    output=[
        {
            "source": {"root": "local", "parts": ["result.score"]},
            "target": {"root": "state", "parts": ["score"]},
        }
    ],
)
```

In an input binding, `path` is a graph source path and `target` is a
node-local input path. In an output binding, `source` is a node-local output
path and `target` is a workflow state destination path.

`in_map`, `input_values`, and `out_map` remain deprecated Python sugar for
concise authoring. Structural path dicts are not valid map keys because Python
dict keys must be hashable. Use canonical binding lists when working from
JSON/MCP or when path segments contain display punctuation.

```json
{
  "root": "state",
  "parts": ["person.name", "three and four"]
}
```

```json
{
  "root": "local",
  "parts": []
}
```

Old strings are accepted at parse boundaries for compatibility. Structural
`parts` are literal field names, so a part may contain dots or spaces without
being split again.
