# OpenAPI Capability Sources

OpenAPI sources expose raw API operations as workflow capabilities.

The OpenAPI document is the source of truth for operation inventory, public
input names, JSON Schema contracts, request paths, request bodies, response
schemas, and declared status codes. Runtime execution uses a generic `httpx`
request builder plus `openapi-core` validation/unmarshalling. It does not parse
generated Python clients and does not rename public OpenAPI fields.

## Payload Shape

Workflow inputs stay OpenAPI-shaped:

```json
{
  "path": {"petId": "pet-1"},
  "query": {"includeOwner": true},
  "header": {"X-Trace-ID": "trace-1"},
  "cookie": {},
  "body": {"name": "Fluffy"}
}
```

The workflow-facing field is `petId`, not a generated Python name like
`pet_id`.

## Outcomes

Raw OpenAPI nodes expose transport-level outcomes:

- `ok`: declared 2xx response and response validation passed.
- `http_error`: declared non-2xx response and response validation passed.
- `unexpected_status`: response status was not declared and no `default`
  response covered it.
- `validation_error`: request or response failed OpenAPI validation.
- `transport_error`: HTTP failed before a response existed.

Business outcomes such as `not_found`, `rate_limited`, or `needs_input` belong
in saved wrappers, not raw OpenAPI operation nodes.

## Current Limits

- Auth integration is future work. For now, source configuration owns the base
  URL only.
- Multipart, form, and binary request/response handling are future work.
- Rich business outcome mapping is wrapper territory.
- OpenAPI operation nodes are workflow capabilities, not top-level MCP tools.
