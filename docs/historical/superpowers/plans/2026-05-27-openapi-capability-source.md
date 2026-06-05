# Superseded OpenAPI Generated-Client Plan

This plan is intentionally retired.

The generated-client approach made runtime execution depend on parsing
`openapi-python-client` generated Python functions to recover parameter-name
mappings such as:

```text
OpenAPI public name: petId
generated Python kwarg: pet_id
```

That dependency direction is too fragile. Do not continue the generated-client
tasks from this file's old history.

Use the replacement plan instead:

```text
docs/historical/superpowers/plans/2026-05-27-openapi-core-capability-source.md
```

The replacement plan uses the OpenAPI document as source of truth,
`openapi-core` for validation/unmarshalling, and a small generic `httpx`
request builder for execution.
