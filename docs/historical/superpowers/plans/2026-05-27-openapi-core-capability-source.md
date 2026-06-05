# OpenAPI Core Capability Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a saved OpenAPI document become a workflow capability source whose operations appear as workflow-facing `NodeSpec`s and execute through spec-driven HTTP requests, without parsing generated Python client code.

**Architecture:** The OpenAPI document is the source of truth for inventory, JSON Schemas, operation paths, parameters, request bodies, and response validation. `openapi-core` validates/unmarshals OpenAPI requests and responses; a small local `httpx` adapter builds and sends HTTP requests from public OpenAPI-shaped payloads. No generated Python client runtime, no AST parsing, and no case-conversion dependency.

**Tech Stack:** Python 3.14, `openapi-core`, `httpx`, existing `jsonschema`, `wf_authoring.NodeSpec`, `wf_platform.CapabilitySource`, `wf_mcp` service registration.

---

## Why This Replaces The Generated-Client Plan

The first plan made the ugly part parameter-name recovery:

```text
OpenAPI/public input: path.petId, header.X-Trace-ID
generated Python fn:  pet_id, x_trace_id
```

Because `openapi-python-client` did not expose a stable operation manifest for those mappings, the implementation parsed generated endpoint functions. That is the wrong dependency direction. We should not inspect generated Python to recover metadata already present in the OpenAPI document.

The revised runtime shape is:

```text
workflow input
  -> OpenAPI-shaped request parts
  -> openapi-core validates/unmarshals request
  -> local httpx request builder sends request
  -> openapi-core validates/unmarshals response
  -> generic workflow outcome
```

This makes validation and execution boring. Outcome mapping remains intentionally generic until saved wrappers add business semantics.

## Non-Goals

- Do not generate Python clients for v1 runtime execution.
- Do not parse generated Python, generated docstrings, or generated function signatures.
- Do not invent a full OpenAPI validator. Use `openapi-core` for request/response validation where possible and `jsonschema` for existing schema-boundary checks.
- Do not make every HTTP status a business outcome. Raw OpenAPI operations expose generic transport outcomes.
- Do not implement custom auth UX in this slice. Leave auth as explicit configuration fields and later integrate with the existing auth/store layer.
- Do not expose every OpenAPI operation as a top-level MCP tool. Expose operations as workflow capabilities first.

## V1 Public Payload Shape

Workflow inputs stay OpenAPI-shaped:

```json
{
  "path": {"petId": "pet-1"},
  "query": {"includeOwner": true},
  "header": {"X-Trace-ID": "abc"},
  "cookie": {},
  "body": {"name": "Ada"}
}
```

No `petId -> pet_id` translation exists because there is no generated Python function.

## V1 Outcome Semantics

Every raw OpenAPI operation node exposes:

```text
ok
http_error
unexpected_status
validation_error
transport_error
```

Rules:

- `ok`: response status is a declared 2xx response and response validation passes.
- `http_error`: response status is a declared non-2xx response and response validation passes.
- `unexpected_status`: response status is not declared and no `default` response covers it.
- `validation_error`: request or response does not match the OpenAPI document.
- `transport_error`: HTTP client raises before a response exists.

Output shape:

```json
{
  "status_code": 200,
  "headers": {},
  "body": {},
  "validation_errors": []
}
```

`body` is JSON when the response is JSON, text for text responses, bytes/base64 later if needed. Keep binary response support out of v1 unless a test fixture forces it.

## Planned File Structure

- Keep: `src/wf_openapi/__init__.py`
  - Public exports for the optional OpenAPI capability-source package.
- Keep/modify: `src/wf_openapi/models.py`
  - Operation/source/execution models. Remove generated-client metadata.
- Keep/modify: `src/wf_openapi/spec.py`
  - Load OpenAPI documents, normalize operations, merge inherited path-item parameters with operation-local overrides.
- Keep/modify: `src/wf_openapi/schemas.py`
  - Produce JSON Schema contracts from effective OpenAPI operation inputs/outputs.
- Replace: `src/wf_openapi/executor.py`
  - Generic `httpx` + `openapi-core` operation executor.
- Remove or repurpose: `src/wf_openapi/codegen.py`
  - Delete generated-client runtime helpers. If kept temporarily, it must not be used by runtime/source tests.
- Create: `src/wf_openapi/request.py`
  - Build method, URL, headers, cookies, query params, and JSON body from OpenAPI-shaped payload.
- Create: `src/wf_openapi/validation.py`
  - Thin adapter between local request/response objects and `openapi-core` protocols.
- Keep/modify: `src/wf_openapi/source.py`
  - Build `CapabilitySource` and `NodeSpec`s using generic execution config.
- Tests:
  - `tests/openapi/test_spec_inventory.py`
  - `tests/openapi/test_schemas.py` if split becomes useful.
  - `tests/openapi/test_request_builder.py`
  - `tests/openapi/test_executor.py`
  - `tests/openapi/test_source.py`

---

## Task 1: Dependency And Plan Reset

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `docs/historical/superpowers/plans/2026-05-27-openapi-capability-source.md`
- Test: `tests/openapi/test_codegen_executor.py` may be removed or replaced later.

- [ ] **Step 1: Replace runtime dependency**

In `pyproject.toml`, remove `openapi-python-client` unless another committed package already uses it. Add:

```toml
"openapi-core>=0.19",
```

Keep `httpx` if already present transitively or directly; add it directly if `wf_openapi` imports it.

- [ ] **Step 2: Refresh lockfile**

Run:

```bash
uv lock
```

Expected: lockfile updates successfully.

- [ ] **Step 3: Mark generated-client plan superseded**

Keep the superseded note at the top of:

```text
docs/historical/superpowers/plans/2026-05-27-openapi-capability-source.md
```

Expected: future agents do not continue Task 5/6 AST parsing work.

- [ ] **Step 4: Verify import availability**

Run:

```bash
uv run python -c "import openapi_core, httpx; print(openapi_core.__name__, httpx.__name__)"
```

Expected: prints `openapi_core httpx`.

---

## Task 2: Remove Generated-Client Runtime Coupling

**Files:**

- Modify: `src/wf_openapi/codegen.py`
- Modify: `src/wf_openapi/executor.py`
- Modify: `tests/openapi/test_codegen_executor.py`

- [ ] **Step 1: Write failing guard test**

Add a test that proves runtime no longer imports generated-client metadata:

```python
def test_openapi_runtime_does_not_require_generated_manifest() -> None:
    from wf_openapi.executor import OpenApiExecutionConfig

    config = OpenApiExecutionConfig(base_url="https://api.example.test")

    assert config.base_url == "https://api.example.test"
    assert not hasattr(config, "generated_package")
    assert not hasattr(config, "operation_modules")
    assert not hasattr(config, "parameter_arguments")
```

Run:

```bash
uv run pytest -q tests/openapi/test_codegen_executor.py::test_openapi_runtime_does_not_require_generated_manifest
```

Expected before implementation: FAIL because generated-client fields still exist.

- [ ] **Step 2: Simplify execution config**

Replace generated-client config with:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenApiExecutionConfig:
    """Runtime config for spec-driven OpenAPI HTTP execution."""

    base_url: str
    timeout_seconds: float = 30.0
```

Do not include generated package/module/parameter mapping fields.

- [ ] **Step 3: Remove generated manifest helpers from runtime path**

Delete or quarantine:

```python
GeneratedOperationMetadata
load_generated_operation_manifest
generate_openapi_client
```

If `codegen.py` remains, its module docstring must say it is experimental/offline tooling and not used by source/executor runtime.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest -q tests/openapi
uv run ruff check src/wf_openapi tests/openapi
uv run basedpyright --level error src/wf_openapi tests/openapi
```

Expected: generated-client tests that no longer match are removed/replaced; remaining tests pass.

---

## Task 3: Generic Request Builder

**Files:**

- Create: `src/wf_openapi/request.py`
- Test: `tests/openapi/test_request_builder.py`

- [ ] **Step 1: Write request builder tests**

Create `tests/openapi/test_request_builder.py`:

```python
from wf_openapi.request import build_http_request_parts
from wf_openapi.spec import load_openapi_operations

FIXTURE = "tests/openapi/fixtures/petstore_minimal.openapi.json"


def test_build_http_request_parts_uses_public_openapi_names() -> None:
    operation = next(op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet")

    parts = build_http_request_parts(
        operation,
        base_url="https://api.example.test/v1",
        payload={
            "path": {"petId": "pet-1"},
            "query": {"includeOwner": True},
            "header": {"X-Trace-ID": "trace-1"},
        },
    )

    assert parts.method == "GET"
    assert parts.url == "https://api.example.test/v1/pets/pet-1"
    assert parts.params["includeOwner"] is True
    assert parts.headers["X-Trace-ID"] == "trace-1"
```

Expected before implementation: FAIL because `wf_openapi.request` does not exist.

- [ ] **Step 2: Implement request parts**

Create:

```python
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import quote

from wf_openapi.models import OpenApiOperation


@dataclass(frozen=True, slots=True)
class HttpRequestParts:
    """OpenAPI-shaped request parts ready for httpx."""

    method: str
    url: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    json: Any | None = None


def build_http_request_parts(
    operation: OpenApiOperation,
    *,
    base_url: str,
    payload: Mapping[str, Any],
) -> HttpRequestParts:
    """Build an HTTP request without renaming public OpenAPI fields."""
    path_values = _mapping(payload, "path")
    path = operation.path
    for parameter in operation.effective_parameters:
        if parameter.get("in") != "path":
            continue
        name = parameter["name"]
        if name not in path_values:
            raise ValueError(f"missing path parameter {name!r}")
        path = path.replace("{" + name + "}", quote(str(path_values[name]), safe=""))

    return HttpRequestParts(
        method=operation.method.upper(),
        url=base_url.rstrip("/") + path,
        params=dict(_mapping(payload, "query")),
        headers={str(k): str(v) for k, v in _mapping(payload, "header").items()},
        cookies={str(k): str(v) for k, v in _mapping(payload, "cookie").items()},
        json=payload.get("body"),
    )


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value
```

- [ ] **Step 3: Add edge tests**

Add tests for:

```text
missing path parameter -> ValueError
non-object query/header/cookie/path -> ValueError
body passes through as json payload
```

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest -q tests/openapi/test_request_builder.py
```

Expected: PASS.

---

## Task 4: openapi-core Validation Adapter

**Files:**

- Create: `src/wf_openapi/validation.py`
- Test: `tests/openapi/test_validation.py`

- [ ] **Step 1: Write validation tests**

Create tests that load the fixture and validate a request built from public payload:

```python
from wf_openapi.request import build_http_request_parts
from wf_openapi.spec import load_openapi, load_openapi_operations
from wf_openapi.validation import validate_openapi_request

FIXTURE = "tests/openapi/fixtures/petstore_minimal.openapi.json"


def test_validate_openapi_request_accepts_public_payload() -> None:
    document = load_openapi(FIXTURE)
    operation = next(op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet")
    parts = build_http_request_parts(
        operation,
        base_url="https://api.example.test",
        payload={"path": {"petId": "pet-1"}},
    )

    result = validate_openapi_request(document, parts)

    assert result.valid is True
    assert result.errors == []
```

Expected before implementation: FAIL because validation adapter does not exist.

- [ ] **Step 2: Implement minimal protocol objects**

Implement local request/response protocol adapters required by `openapi-core`. Keep them in `validation.py` and document that they are intentionally thin protocol shims.

The adapter must carry:

```text
method
full_url_pattern or path pattern if required by openapi-core
parameters/path/query/header/cookie
body
mimetype
```

If `openapi-core` requires a different protocol shape, adapt only this file.

- [ ] **Step 3: Validate response path**

Add:

```python
def validate_openapi_response(document, request_parts, response_parts) -> ValidationResult:
    ...
```

Test declared `200` response and undeclared status behavior.

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest -q tests/openapi/test_validation.py
uv run basedpyright --level error src/wf_openapi/validation.py tests/openapi/test_validation.py
```

Expected: PASS.

---

## Task 5: Generic HTTP Executor

**Files:**

- Modify: `src/wf_openapi/executor.py`
- Test: `tests/openapi/test_executor.py`

- [ ] **Step 1: Write executor tests with mocked transport**

Use `httpx.MockTransport`:

```python
import httpx

from wf_openapi.executor import OpenApiExecutionConfig, call_openapi_operation
from wf_openapi.spec import load_openapi, load_openapi_operations

FIXTURE = "tests/openapi/fixtures/petstore_minimal.openapi.json"


async def test_call_openapi_operation_maps_success() -> None:
    document = load_openapi(FIXTURE)
    operation = next(op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pets/pet-1"
        return httpx.Response(200, json={"id": "pet-1"})

    result = await call_openapi_operation(
        document,
        operation,
        OpenApiExecutionConfig(base_url="https://api.example.test"),
        {"path": {"petId": "pet-1"}},
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    assert result.outcome == "ok"
    assert result.value.status_code == 200
    assert result.value.body["id"] == "pet-1"
```

Expected before implementation: FAIL because executor still uses generated client or wrong signature.

- [ ] **Step 2: Implement executor**

`call_openapi_operation(...)` should:

```text
build request parts
validate/unmarshal request
send with httpx.AsyncClient
parse response body by content-type
validate/unmarshal response
return NodeReturn with generic outcome
```

Transport exceptions become `transport_error`. Validation failures become `validation_error`.

- [ ] **Step 3: Add outcome tests**

Add tests for:

```text
declared non-2xx -> http_error
undeclared status -> unexpected_status
invalid request -> validation_error
httpx transport exception -> transport_error
```

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest -q tests/openapi/test_executor.py
```

Expected: PASS.

---

## Task 6: Source Integration

**Files:**

- Modify: `src/wf_openapi/source.py`
- Test: `tests/openapi/test_source.py`

- [ ] **Step 1: Write source execution test**

Build a `CapabilitySource`, get `source.capabilities.node_specs["petstore.default.get_pet"]`, call its async handler with public payload, and use `httpx.MockTransport` through runtime/config injection.

Expected before implementation: FAIL because source still uses generated metadata or does not pass executor dependencies.

- [ ] **Step 2: Update source builder**

`build_openapi_capability_source(...)` should accept:

```python
document_path: Path
source_id: str
base_url: str
```

It should not accept:

```text
generated_package
operation_modules
parameter_arguments
```

- [ ] **Step 3: Preserve schema contracts**

Ensure each `NodeSpec` still exposes:

```text
input_schema_contract from operation input schema
output_schema_contract from operation output schema
outcomes = ("ok", "http_error", "unexpected_status", "validation_error", "transport_error")
```

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest -q tests/openapi/test_source.py
```

Expected: PASS.

---

## Task 7: Docs And Final Cleanup

**Files:**

- Create: `docs/openapi_capability_source.md`
- Modify: `docs/current_roadmap.md`
- Delete or rewrite: generated-client-only tests/files if no longer used.

- [ ] **Step 1: Document the boundary**

Create `docs/openapi_capability_source.md` with:

```markdown
# OpenAPI Capability Sources

OpenAPI sources expose raw API operations as workflow capabilities.

The OpenAPI document is the source of truth. Runtime execution uses a generic
httpx request builder and openapi-core validation. The runtime does not parse
generated Python clients and does not rename public OpenAPI fields.

Raw OpenAPI nodes expose generic transport outcomes. Saved wrappers should add
business-specific outcomes such as `not_found`, `rate_limited`, or
`needs_input`.
```

- [ ] **Step 2: Note deferred auth/body/binary support**

Document:

```text
auth integration: future
binary/multipart request bodies: future
rich outcome mapping: wrappers, not raw operations
```

- [ ] **Step 3: Final verification**

Run:

```bash
uv run pytest -q tests/openapi
uv run ruff check src/wf_openapi tests/openapi
uv run ruff format --check src/wf_openapi tests/openapi
uv run basedpyright --level error src/wf_openapi tests/openapi
```

Expected: all pass.

---

## Self-Review

- The plan no longer requires generated Python client parsing.
- Public OpenAPI names remain public workflow names.
- Validation is library-backed through `openapi-core`, not hand-rolled.
- HTTP execution is locally owned but small and testable with `httpx.MockTransport`.
- Outcome mapping stays generic and wrapper-friendly.
- Auth, multipart/binary, and business outcomes are deferred explicitly.
