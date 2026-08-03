# Workflow Contract Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate, validate, check in, and drift-check a deterministic transport-neutral manifest for the complete Python workflow OpenRPC contract.

**Architecture:** A new Python tooling package composes the real local workflow server, extracts its OpenRPC document, and passes it through a pure fail-closed normalizer. Canonical JSON I/O and a small module CLI own the checked artifact; a focused integration test makes Python contract drift visible without changing the TypeScript runtime or browser allowlist.

**Tech Stack:** Python 3.14, `fastapi-jsonrpc` OpenRPC output, `TypedDict`, standard-library `argparse` and `json`, pytest, Ruff, basedpyright

## Global Constraints

- Implement only the checked manifest and deterministic drift gate described in [`workflow contract manifest design`](../specs/2026-08-01-workflow-contract-manifest-design.md).
- Do not modify `web/`, generate TypeScript, translate JSON Schema to Effect Schema, upgrade Effect, add an HTTP endpoint, or expand the browser operation allowlist.
- The manifest must describe every server operation without authorizing any caller to use it.
- The full dotted method name is canonical identity; derived `namespace` and `action` are navigation metadata only.
- Sort operations by method and component dictionaries by key; preserve OpenRPC parameter order.
- Recursively remove only generated JSON Schema `title` keys. Preserve all other schema keywords, `{}`, optionality, nullability, and absent/`true`/`false` `additionalProperties` exactly.
- Preserve local `$ref` values. Reject external references, dangling references, and references into unsupported component namespaces.
- Treat `70` methods, `126` schemas, one declared error, and the five known union result components as initial baseline assertions, not hard generator limits.
- `check` must compare bytes and never rewrite the checked artifact.
- Use a temporary local workflow store. No temporary path, target URL, RPC path, credential, header, or environment-specific value may enter the manifest.
- Add docstrings or comments at the non-obvious recursive-normalization, reference-validation, and temporary-server seams.
- Use `tmp_path` in tests and scoped pytest commands with `-n 0`.
- Do not modify `.serena/` or Serena configuration.

---

### Task 1: Pure Manifest Model And Normalization

**Files:**
- Create: `src/wf_contract_manifest/__init__.py`
- Create: `src/wf_contract_manifest/model.py`
- Create: `src/wf_contract_manifest/normalize.py`
- Create: `tests/wf_contract_manifest/__init__.py`
- Create: `tests/wf_contract_manifest/fixtures.py`
- Create: `tests/wf_contract_manifest/test_normalize.py`

**Interfaces:**
- Consumes: an OpenRPC document as `Mapping[str, object]`.
- Produces: `ManifestError`, `JsonValue`, `JsonSchema`, `ContractManifest`, and `manifest_from_openrpc(document: Mapping[str, object]) -> ContractManifest`.
- Contract: this task validates the manifest envelope and normalizes valid operations; Task 2 adds complete reference-graph validation.

- [x] **Step 1: Add the reusable synthetic OpenRPC fixture**

Create `tests/wf_contract_manifest/fixtures.py` with a fixture that deliberately exercises ordering and schema preservation:

```python
from __future__ import annotations

from typing import Any


def synthetic_openrpc_document() -> dict[str, Any]:
    return {
        "openrpc": "1.2.6",
        "info": {"title": "ignored", "version": "0"},
        "methods": [
            {
                "name": "workflow.zeta.run",
                "params": [],
                "result": {
                    "name": "workflow.zeta.run_Result",
                    "schema": {"$ref": "#/components/schemas/ZetaResult"},
                },
                "errors": [{"$ref": "#/components/errors/5000"}],
            },
            {
                "name": "workflow.alpha.inspect",
                "params": [
                    {
                        "name": "optional_nullable",
                        "required": False,
                        "schema": {
                            "title": "Optional Nullable",
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "x-future-keyword": {"title": "removed recursively", "value": 1},
                        },
                    },
                    {
                        "name": "required_closed",
                        "required": True,
                        "schema": {
                            "title": "Required Closed",
                            "type": "object",
                            "additionalProperties": False,
                        },
                    },
                ],
                "result": {
                    "name": "workflow.alpha.inspect_Result",
                    "schema": {"$ref": "#/components/schemas/AlphaResult"},
                },
                "errors": [{"$ref": "#/components/errors/5000"}],
            },
        ],
        "components": {
            "schemas": {
                "ZetaResult": {
                    "title": "Zeta Result",
                    "type": "object",
                    "properties": {"extension": {"additionalProperties": True}},
                },
                "FreeJson": {},
                "AlphaResult": {
                    "title": "Alpha Result",
                    "type": "object",
                    "properties": {
                        "mode": {"title": "Mode", "const": "alpha"},
                        "payload": {},
                    },
                    "required": ["mode", "payload"],
                    "if": {"properties": {"mode": {"const": "alpha"}}},
                    "then": {"required": ["payload"]},
                    "not": {"required": ["forbidden"]},
                },
            },
            "errors": {
                "5000": {
                    "code": 5000,
                    "message": "Workflow operation failed",
                    "data": {
                        "title": "Error Data",
                        "type": "object",
                        "additionalProperties": False,
                    },
                }
            },
        },
    }
```

- [x] **Step 2: Write failing happy-path normalization tests**

Create `tests/wf_contract_manifest/test_normalize.py`:

```python
from __future__ import annotations

from wf_contract_manifest import manifest_from_openrpc

from .fixtures import synthetic_openrpc_document


def test_normalizes_operations_and_components_deterministically() -> None:
    manifest = manifest_from_openrpc(synthetic_openrpc_document())

    assert manifest["manifest_version"] == 1
    assert manifest["source"] == {
        "format": "openrpc",
        "openrpc_version": "1.2.6",
    }
    assert [operation["method"] for operation in manifest["operations"]] == [
        "workflow.alpha.inspect",
        "workflow.zeta.run",
    ]
    assert list(manifest["components"]["schemas"]) == [
        "AlphaResult",
        "FreeJson",
        "ZetaResult",
    ]
    assert list(manifest["components"]["errors"]) == ["5000"]


def test_preserves_parameter_order_optionality_and_nullability() -> None:
    operation = manifest_from_openrpc(synthetic_openrpc_document())["operations"][0]

    assert [parameter["name"] for parameter in operation["params"]] == [
        "optional_nullable",
        "required_closed",
    ]
    assert operation["params"][0]["required"] is False
    assert operation["params"][0]["schema"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert operation["params"][1]["required"] is True
    assert operation["params"][1]["schema"]["additionalProperties"] is False


def test_removes_only_titles_and_preserves_unknown_schema_keywords() -> None:
    manifest = manifest_from_openrpc(synthetic_openrpc_document())
    optional_schema = manifest["operations"][0]["params"][0]["schema"]

    assert "title" not in optional_schema
    assert optional_schema["x-future-keyword"] == {"value": 1}
    assert manifest["components"]["schemas"]["FreeJson"] == {}
    assert manifest["components"]["schemas"]["ZetaResult"]["properties"] == {
        "extension": {"additionalProperties": True}
    }


def test_preserves_conditional_schema_keywords() -> None:
    alpha = manifest_from_openrpc(synthetic_openrpc_document())["components"]["schemas"][
        "AlphaResult"
    ]

    assert alpha["if"] == {"properties": {"mode": {"const": "alpha"}}}
    assert alpha["then"] == {"required": ["payload"]}
    assert alpha["not"] == {"required": ["forbidden"]}
```

- [x] **Step 3: Run the tests and confirm the package is missing**

Run:

```powershell
New-Item -ItemType Directory -Force -Path '.pytest-tmp\manifest-task1' | Out-Null
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_normalize.py -n 0 --basetemp '.pytest-tmp\manifest-task1' -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'wf_contract_manifest'`.

- [x] **Step 4: Add the typed manifest model**

Create `src/wf_contract_manifest/model.py` with these public definitions:

```python
from __future__ import annotations

from typing import TypedDict

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonSchema = dict[str, JsonValue]


class ManifestSource(TypedDict):
    format: str
    openrpc_version: str


class ManifestParameter(TypedDict):
    name: str
    required: bool
    schema: JsonSchema


class ManifestResult(TypedDict):
    schema: JsonSchema


class ManifestOperation(TypedDict):
    method: str
    namespace: list[str]
    action: str
    params: list[ManifestParameter]
    result: ManifestResult
    errors: list[JsonSchema]


class ManifestComponents(TypedDict):
    schemas: dict[str, JsonSchema]
    errors: dict[str, JsonValue]


class ContractManifest(TypedDict):
    manifest_version: int
    source: ManifestSource
    operations: list[ManifestOperation]
    components: ManifestComponents


class ManifestError(ValueError):
    """Report an invalid source contract with its exact OpenRPC document path."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")
```

Create `src/wf_contract_manifest/__init__.py` as the public tooling facade:

```python
from .model import ContractManifest, JsonSchema, JsonValue, ManifestError
from .normalize import manifest_from_openrpc

__all__ = [
    "ContractManifest",
    "JsonSchema",
    "JsonValue",
    "ManifestError",
    "manifest_from_openrpc",
]
```

- [x] **Step 5: Implement the minimal pure normalizer**

Create `src/wf_contract_manifest/normalize.py`. Keep the envelope readers small and path-aware. The implementation must:

```python
from __future__ import annotations

from collections.abc import Mapping

from .model import (
    ContractManifest,
    JsonSchema,
    JsonValue,
    ManifestError,
    ManifestOperation,
    ManifestParameter,
)


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ManifestError(path, "expected an object")
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ManifestError(path, "expected an array")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(path, "expected a non-empty string")
    return value


def _json_value(value: object, path: str) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ManifestError(path, "expected string object keys")
            if key != "title":
                normalized[key] = _json_value(item, f"{path}.{key}")
        return normalized
    raise ManifestError(path, "expected a JSON value")


def _schema(value: object, path: str) -> JsonSchema:
    normalized = _json_value(value, path)
    if not isinstance(normalized, dict):
        raise ManifestError(path, "expected a schema object")
    return normalized
```

Then implement `manifest_from_openrpc()` using the helpers above:

- require a non-empty string at `$.openrpc`;
- require arrays/objects at `$.methods`, `$.components`, `$.components.schemas`, and `$.components.errors`;
- require each method name to contain at least one `.` and have no empty segments;
- derive `namespace = segments[:-1]` and `action = segments[-1]`;
- require each parameter's `name`, boolean `required`, and object `schema`;
- retain only normalized `schema` under `result` and each error entry;
- sort operations by `method` and component items by key;
- construct the exact `ContractManifest` shape in the approved spec.

Use a short comment over `_json_value`: generated titles are removed recursively, while every other schema keyword and value is intentionally opaque.

- [x] **Step 6: Run focused tests and static checks**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_normalize.py -n 0 --basetemp '.pytest-tmp\manifest-task1' -q
.venv\Scripts\ruff.exe check src\wf_contract_manifest tests\wf_contract_manifest
.venv\Scripts\basedpyright.exe --level error src\wf_contract_manifest tests\wf_contract_manifest
```

Expected: all normalization tests pass; Ruff and basedpyright report no errors.

- [x] **Step 7: Commit Task 1**

```powershell
git add src\wf_contract_manifest tests\wf_contract_manifest
git commit -m "feat: normalize workflow OpenRPC manifests"
```

---

### Task 2: Fail-Closed Contract And Reference Validation

**Files:**
- Modify: `src/wf_contract_manifest/normalize.py`
- Modify: `tests/wf_contract_manifest/test_normalize.py`

**Interfaces:**
- Consumes: `ManifestError`, normalized operation/component values from Task 1.
- Produces: the same `manifest_from_openrpc()` interface, now rejecting malformed methods and invalid `$ref` graphs before returning.

- [x] **Step 1: Add failing malformed-envelope tests**

Append parameterized tests to `tests/wf_contract_manifest/test_normalize.py`:

```python
from copy import deepcopy

import pytest

from wf_contract_manifest import ManifestError


@pytest.mark.parametrize(
    ("mutate", "path", "message"),
    [
        (
            lambda document: document.update({"openrpc": "2.0.0"}),
            "$.openrpc",
            "unsupported OpenRPC version '2.0.0'; expected '1.2.6'",
        ),
        (lambda document: document.update({"methods": {}}), "$.methods", "expected an array"),
        (
            lambda document: document["methods"].append(deepcopy(document["methods"][0])),
            "$.methods[2].name",
            "duplicate method 'workflow.zeta.run'",
        ),
        (
            lambda document: document["methods"][0].update({"name": "workflow..run"}),
            "$.methods[0].name",
            "malformed dotted method name",
        ),
        (
            lambda document: document["methods"][0].update({"params": {}}),
            "$.methods[0].params",
            "expected an array",
        ),
        (
            lambda document: document["methods"][0]["params"].append(
                {"name": "value", "required": "yes", "schema": {"type": "string"}}
            ),
            "$.methods[0].params[0].required",
            "expected a boolean",
        ),
        (
            lambda document: document["methods"][0].update({"result": {}}),
            "$.methods[0].result.schema",
            "expected an object",
        ),
        (
            lambda document: document["methods"][0]["result"].update(
                {"schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}}}
            ),
            "$.methods[0].result.schema",
            "success result must reference a named schema component",
        ),
    ],
)
def test_rejects_malformed_openrpc_contracts(mutate, path: str, message: str) -> None:
    document = synthetic_openrpc_document()
    mutate(document)

    with pytest.raises(ManifestError) as exc_info:
        manifest_from_openrpc(document)

    assert exc_info.value.path == path
    assert exc_info.value.message == message
```

If basedpyright rejects untyped lambdas, define a `Protocol` named `DocumentMutation` and annotate the parameter, or replace the table with named mutation functions. Do not silence it with `Any` casts.

- [x] **Step 2: Add failing reference-graph tests**

Add tests for every rejected reference class:

```python
@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("https://example.test/schema.json", "external references are not supported"),
        ("#/definitions/Result", "unsupported local reference namespace"),
        ("#/components/parameters/Value", "unsupported component reference namespace"),
        ("#/components/schemas/Missing", "dangling local reference"),
    ],
)
def test_rejects_unsupported_or_dangling_references(
    reference: str,
    message: str,
) -> None:
    document = synthetic_openrpc_document()
    document["components"]["schemas"]["AlphaResult"]["properties"]["linked"] = {
        "$ref": reference
    }

    with pytest.raises(ManifestError) as exc_info:
        manifest_from_openrpc(document)

    assert exc_info.value.path.endswith(".properties.linked.$ref")
    assert exc_info.value.message == message


def test_accepts_nested_schema_and_error_component_references() -> None:
    document = synthetic_openrpc_document()
    document["components"]["schemas"]["AlphaResult"]["properties"]["linked"] = {
        "$ref": "#/components/schemas/ZetaResult"
    }

    manifest = manifest_from_openrpc(document)

    assert manifest["operations"][0]["errors"] == [
        {"$ref": "#/components/errors/5000"}
    ]
```

- [x] **Step 3: Run tests and verify fail-closed cases are red**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_normalize.py -n 0 --basetemp '.pytest-tmp\manifest-task2' -q
```

Expected: new duplicate-method, generic-result, and invalid-reference cases fail because Task 1 does not yet reject them.

- [x] **Step 4: Implement strict method/result validation**

In `normalize.py`:

- require `$.openrpc` to equal `"1.2.6"`; a new OpenRPC format version must be reviewed before manifest v1 accepts it;
- add `_boolean(value: object, path: str) -> bool` that rejects non-`bool` values;
- maintain `seen_methods: set[str]` while reading methods and report duplicates at the later method's `.name` path;
- validate dotted names with `parts = method.split(".")` and reject `len(parts) < 2` or any empty part;
- require every success schema to be exactly a local schema reference object at the top level: `set(schema) == {"$ref"}` and `schema["$ref"]` begins with `#/components/schemas/`.

This top-level result rule is intentionally stricter than nested JSON Schema. Every current successful operation has a named result component, which is the stable seam the TypeScript generator will consume.

- [x] **Step 5: Implement one complete reference-graph walk**

Add these internal interfaces:

```python
type ComponentIndex = dict[str, set[str]]


def _walk_references(value: JsonValue, path: str):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "$ref":
                if not isinstance(child, str):
                    raise ManifestError(child_path, "expected a reference string")
                yield child_path, child
            else:
                yield from _walk_references(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_references(child, f"{path}[{index}]")
```

Use a docstring explaining that this walker intentionally treats JSON Schema vocabulary as opaque and inspects only `$ref` values.

Build a component index from normalized keys:

```python
component_index: ComponentIndex = {
    "schemas": set(manifest["components"]["schemas"]),
    "errors": set(manifest["components"]["errors"]),
}
```

For every operation and component value, walk references and validate:

1. references must start with `#/`;
2. split path must be exactly `components/<schemas|errors>/<key>`;
3. JSON Pointer unescaping is not supported in v1, so reject keys containing `~0` or `~1` with `unsupported escaped component reference`;
4. the component key must exist in the indexed namespace.

Run this validation once after the whole manifest is assembled so forward references are valid.

- [x] **Step 6: Run focused tests and static checks**

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_normalize.py -n 0 --basetemp '.pytest-tmp\manifest-task2' -q
.venv\Scripts\ruff.exe check src\wf_contract_manifest tests\wf_contract_manifest
.venv\Scripts\basedpyright.exe --level error src\wf_contract_manifest tests\wf_contract_manifest
```

Expected: all normalization and validation tests pass; static checks are clean.

- [x] **Step 7: Commit Task 2**

```powershell
git add src\wf_contract_manifest\normalize.py tests\wf_contract_manifest\test_normalize.py
git commit -m "feat: validate workflow contract references"
```

---

### Task 3: Real Contract Generation And Canonical I/O

**Files:**
- Create: `src/wf_contract_manifest/generate.py`
- Create: `src/wf_contract_manifest/io.py`
- Create: `tests/wf_contract_manifest/test_generate.py`
- Create: `tests/wf_contract_manifest/test_io.py`
- Modify: `src/wf_contract_manifest/__init__.py`

**Interfaces:**
- Consumes: `manifest_from_openrpc()` from Tasks 1-2, `wf_server.build_local_static_workflow_server`, and `wf_transport_rpc_http.create_rpc_app`.
- Produces: `generate_manifest() -> ContractManifest`, `canonical_manifest_json(manifest) -> str`, `write_manifest(manifest, path) -> Path`, `check_manifest(manifest, path) -> None`, `ManifestDriftError`, and `DEFAULT_MANIFEST_PATH`.

- [x] **Step 1: Write the real-contract integration test**

Create `tests/wf_contract_manifest/test_generate.py`:

```python
from __future__ import annotations

from wf_contract_manifest import generate_manifest


UNION_RESULTS = {
    "InspectCapabilityResult",
    "PatchDraftResult",
    "ValidateDraftResult",
    "CompileDraftWorkspaceResult",
    "CreateArtifactFromWorkspaceResult",
}


def test_generates_the_complete_real_workflow_contract() -> None:
    manifest = generate_manifest()
    schemas = manifest["components"]["schemas"]

    assert len(manifest["operations"]) == 70
    assert len({operation["method"] for operation in manifest["operations"]}) == 70
    assert len(schemas) == 126
    assert len(manifest["components"]["errors"]) == 1
    assert all(set(operation["result"]["schema"]) == {"$ref"} for operation in manifest["operations"])
    assert {name for name in UNION_RESULTS if "anyOf" in schemas[name]} == UNION_RESULTS


def test_generated_contract_preserves_security_and_extension_boundaries() -> None:
    schemas = generate_manifest()["components"]["schemas"]

    auth_result_names = [name for name in schemas if "Auth" in name and name.endswith("Result")]
    assert auth_result_names
    for name in auth_result_names:
        properties = schemas[name].get("properties", {})
        assert isinstance(properties, dict)
        assert "payload" not in properties

    assert schemas["SourceDiagnosisResult"]["additionalProperties"] is True
    assert schemas["RegistryEntryPayload"]["additionalProperties"] is True


def test_generated_contract_contains_no_temporary_or_transport_state() -> None:
    serialized = str(generate_manifest())

    assert "TemporaryDirectory" not in serialized
    assert "\\\\Temp\\\\" not in serialized
    assert "127.0.0.1" not in serialized
    assert '"/rpc"' not in serialized
```

If current auth result components use a narrower naming convention, replace `auth_result_names` with the exact current component names discovered from the real document and pin them explicitly. Do not weaken the assertion to a no-op.

- [x] **Step 2: Write canonical I/O tests**

Create `tests/wf_contract_manifest/test_io.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from wf_contract_manifest import (
    ManifestDriftError,
    canonical_manifest_json,
    check_manifest,
    manifest_from_openrpc,
    write_manifest,
)

from .fixtures import synthetic_openrpc_document


def _manifest():
    return manifest_from_openrpc(synthetic_openrpc_document())


def test_canonical_json_is_stable_utf8_text_with_trailing_newline() -> None:
    first = canonical_manifest_json(_manifest())
    second = canonical_manifest_json(_manifest())

    assert first == second
    assert first.endswith("\n")
    assert '  "manifest_version": 1' in first
    assert "\\u" not in first


def test_write_and_check_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "workflow-api.manifest.json"

    assert write_manifest(_manifest(), path) == path
    check_manifest(_manifest(), path)

    assert path.read_bytes() == canonical_manifest_json(_manifest()).encode("utf-8")


def test_check_reports_drift_without_mutating_the_file(tmp_path: Path) -> None:
    path = tmp_path / "workflow-api.manifest.json"
    path.write_text("stale\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ManifestDriftError, match="python -m wf_contract_manifest write"):
        check_manifest(_manifest(), path)

    assert path.read_bytes() == before
```

- [x] **Step 3: Run tests and verify generation/I/O modules are missing**

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_generate.py tests\wf_contract_manifest\test_io.py -n 0 --basetemp '.pytest-tmp\manifest-task3' -q
```

Expected: collection fails because `generate_manifest`, `ManifestDriftError`, and the I/O helpers are not exported.

- [x] **Step 4: Implement real in-process generation**

Create `src/wf_contract_manifest/generate.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import create_rpc_app

from .model import ContractManifest
from .normalize import manifest_from_openrpc


def generate_manifest() -> ContractManifest:
    """Compose the real server against an isolated store and normalize OpenRPC."""
    with TemporaryDirectory(prefix="wf-contract-manifest-") as directory:
        server = build_local_static_workflow_server(Path(directory) / "store")
        document = cast(dict[str, object], create_rpc_app(server).get_openrpc())
        # Normalization deliberately drops framework metadata that could carry
        # process-local paths or transport details.
        return manifest_from_openrpc(document)
```

Do not start Uvicorn, bind a socket, read `.env`, or construct a remote client. The composed in-process app is the authoritative transport registration surface.

- [x] **Step 5: Implement byte-canonical I/O**

Create `src/wf_contract_manifest/io.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .model import ContractManifest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "contracts" / "workflow-api.manifest.json"


class ManifestDriftError(RuntimeError):
    """Indicate that the checked manifest differs from the generated contract."""


def canonical_manifest_json(manifest: ContractManifest) -> str:
    try:
        return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    except (TypeError, ValueError) as error:
        raise ValueError(f"manifest is not canonically serializable: {error}") from error


def write_manifest(manifest: ContractManifest, path: Path = DEFAULT_MANIFEST_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_manifest_json(manifest), encoding="utf-8", newline="\n")
    return path


def check_manifest(manifest: ContractManifest, path: Path = DEFAULT_MANIFEST_PATH) -> None:
    expected = canonical_manifest_json(manifest).encode("utf-8")
    try:
        actual = path.read_bytes()
    except FileNotFoundError as error:
        raise ManifestDriftError(
            f"{path} is missing; run `python -m wf_contract_manifest write`"
        ) from error
    if actual != expected:
        raise ManifestDriftError(
            f"{path} is stale; run `python -m wf_contract_manifest write`"
        )
```

Byte comparison is intentional: it catches semantic contract drift and non-canonical manual edits with the same deterministic remediation.

- [x] **Step 6: Export the generation and I/O interfaces**

Update `src/wf_contract_manifest/__init__.py` so `__all__` also contains:

```python
from .generate import generate_manifest
from .io import (
    DEFAULT_MANIFEST_PATH,
    ManifestDriftError,
    canonical_manifest_json,
    check_manifest,
    write_manifest,
)
```

- [x] **Step 7: Run focused tests and static checks**

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest -n 0 --basetemp '.pytest-tmp\manifest-task3' -q
.venv\Scripts\ruff.exe check src\wf_contract_manifest tests\wf_contract_manifest
.venv\Scripts\basedpyright.exe --level error src\wf_contract_manifest tests\wf_contract_manifest
```

Expected: synthetic and real-contract tests pass; static checks are clean.

- [x] **Step 8: Commit Task 3**

```powershell
git add src\wf_contract_manifest tests\wf_contract_manifest
git commit -m "feat: generate canonical workflow contract"
```

---

### Task 4: Module CLI And Checked Manifest Artifact

**Files:**
- Create: `src/wf_contract_manifest/__main__.py`
- Create: `tests/wf_contract_manifest/test_cli.py`
- Create by command: `contracts/workflow-api.manifest.json`

**Interfaces:**
- Consumes: `generate_manifest`, `write_manifest`, `check_manifest`, `DEFAULT_MANIFEST_PATH`, and `ManifestDriftError` from Task 3.
- Produces: `main(argv: Sequence[str] | None = None) -> int` and the supported commands `.venv\Scripts\python.exe -m wf_contract_manifest write|check`.

- [x] **Step 1: Write CLI behavior tests**

Create `tests/wf_contract_manifest/test_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from wf_contract_manifest import ContractManifest, ManifestDriftError, manifest_from_openrpc
from wf_contract_manifest.__main__ import main

from .fixtures import synthetic_openrpc_document


def _manifest() -> ContractManifest:
    return manifest_from_openrpc(synthetic_openrpc_document())


def test_write_generates_once_and_writes_requested_contract(monkeypatch, tmp_path: Path) -> None:
    manifest = _manifest()
    calls: list[tuple[object, Path]] = []
    monkeypatch.setattr("wf_contract_manifest.__main__.generate_manifest", lambda: manifest)
    monkeypatch.setattr(
        "wf_contract_manifest.__main__.write_manifest",
        lambda value, path: calls.append((value, path)) or path,
    )
    monkeypatch.setattr("wf_contract_manifest.__main__.DEFAULT_MANIFEST_PATH", tmp_path / "manifest.json")

    assert main(["write"]) == 0
    assert calls == [(manifest, tmp_path / "manifest.json")]


def test_check_returns_nonzero_and_prints_drift_guidance(monkeypatch, capsys) -> None:
    monkeypatch.setattr("wf_contract_manifest.__main__.generate_manifest", _manifest)

    def fail_check(_manifest, _path) -> None:
        raise ManifestDriftError("stale; run `python -m wf_contract_manifest write`")

    monkeypatch.setattr("wf_contract_manifest.__main__.check_manifest", fail_check)

    assert main(["check"]) == 1
    assert "python -m wf_contract_manifest write" in capsys.readouterr().err


def test_rejects_unknown_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["unknown"])

    assert exc_info.value.code == 2
```

Use explicit pytest fixture types already established in the repository if basedpyright requires them; do not replace behavior assertions with subprocess-only smoke tests.

- [x] **Step 2: Run the CLI test and confirm it is red**

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_cli.py -n 0 --basetemp '.pytest-tmp\manifest-task4' -q
```

Expected: collection fails because `wf_contract_manifest.__main__` does not exist.

- [x] **Step 3: Implement the module CLI**

Create `src/wf_contract_manifest/__main__.py`:

```python
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .generate import generate_manifest
from .io import DEFAULT_MANIFEST_PATH, ManifestDriftError, check_manifest, write_manifest
from .model import ManifestError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the checked workflow API contract manifest.")
    parser.add_argument("command", choices=("write", "check"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = generate_manifest()
        if args.command == "write":
            path = write_manifest(manifest, DEFAULT_MANIFEST_PATH)
            print(f"wrote {path}")
        else:
            check_manifest(manifest, DEFAULT_MANIFEST_PATH)
            print(f"checked {DEFAULT_MANIFEST_PATH}")
    except (ManifestError, ManifestDriftError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Do not add a `[project.scripts]` entry. The approved surface is the module command.

- [x] **Step 4: Run the CLI test and static checks**

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_cli.py -n 0 --basetemp '.pytest-tmp\manifest-task4' -q
.venv\Scripts\ruff.exe check src\wf_contract_manifest tests\wf_contract_manifest
.venv\Scripts\basedpyright.exe --level error src\wf_contract_manifest tests\wf_contract_manifest
```

Expected: CLI tests pass and static checks are clean.

- [x] **Step 5: Generate and independently check the committed artifact**

```powershell
.venv\Scripts\python.exe -m wf_contract_manifest write
.venv\Scripts\python.exe -m wf_contract_manifest check
```

Expected: the first command reports `contracts\workflow-api.manifest.json` written; the second reports the same path checked and exits zero.

Inspect the artifact with bounded assertions rather than manually reading thousands of lines:

```powershell
@'
import json
from pathlib import Path
path = Path("contracts/workflow-api.manifest.json")
manifest = json.loads(path.read_text(encoding="utf-8"))
print(len(manifest["operations"]))
print(len(manifest["components"]["schemas"]))
print(len(manifest["components"]["errors"]))
print(manifest["operations"][0]["method"])
print(manifest["operations"][-1]["method"])
'@ | .venv\Scripts\python.exe -
```

Expected: `70`, `126`, `1`, followed by the lexically first and last method names.

- [x] **Step 6: Commit Task 4**

```powershell
git add src\wf_contract_manifest\__main__.py tests\wf_contract_manifest\test_cli.py contracts\workflow-api.manifest.json
git commit -m "feat: check in workflow contract manifest"
```

---

### Task 5: Drift Gate, Documentation, And Final Review

**Files:**
- Create: `tests/wf_contract_manifest/test_committed_manifest.py`
- Modify: `ISSUES.md`
- Modify: `docs/project_map.md`
- Modify: `docs/current_roadmap.md`
- Move after implementation: `docs/superpowers/plans/2026-08-01-workflow-contract-manifest.md` to `docs/historical/superpowers/plans/2026-08-01-workflow-contract-manifest.md`

**Interfaces:**
- Consumes: the real generator, canonical checker, and checked artifact from Tasks 3-4.
- Produces: a deterministic pytest drift gate and current documentation pointing to the manifest seam and the next TypeScript generation slice.

- [x] **Step 1: Write the committed-manifest drift test**

Create `tests/wf_contract_manifest/test_committed_manifest.py`:

```python
from wf_contract_manifest import DEFAULT_MANIFEST_PATH, check_manifest, generate_manifest


def test_committed_manifest_matches_the_python_workflow_contract() -> None:
    check_manifest(generate_manifest(), DEFAULT_MANIFEST_PATH)
```

- [x] **Step 2: Prove the drift gate fails without mutating the artifact**

Use a temporary backup and restore in one PowerShell `try/finally` block:

```powershell
$path = Resolve-Path 'contracts\workflow-api.manifest.json'
$before = [System.IO.File]::ReadAllBytes($path)
try {
  Add-Content -LiteralPath $path -Value ' '
  .venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_committed_manifest.py -n 0 --basetemp '.pytest-tmp\manifest-task5-red' -q
  if ($LASTEXITCODE -eq 0) { throw 'drift test unexpectedly passed' }
} finally {
  [System.IO.File]::WriteAllBytes($path, $before)
}
```

Expected: pytest fails with `ManifestDriftError` and guidance to run `python -m wf_contract_manifest write`; the `finally` block restores the exact original bytes.

- [x] **Step 3: Run the restored drift gate**

```powershell
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_committed_manifest.py -n 0 --basetemp '.pytest-tmp\manifest-task5-green' -q
```

Expected: one test passes.

- [x] **Step 4: Update current documentation**

Read `docs/AGENTS.md` before editing these files.

In `ISSUES.md`, update the TypeScript JSON-RPC coverage section to record:

- all 70 Python methods now have named OpenRPC success schemas;
- `contracts/workflow-api.manifest.json` is the checked transport-neutral inventory;
- `python -m wf_contract_manifest check` is the drift gate;
- browser authorization, operation metadata, and the 12 current Effect RPC implementations remain authored boundaries; and
- the next slice is generated TypeScript operation names/raw types plus a fail-closed representative JSON Schema-to-Effect translator.

In the package table in `docs/project_map.md`, add:

```markdown
| `wf_contract_manifest` | Tooling that normalizes the composed workflow OpenRPC document into the checked transport-neutral contract manifest and detects drift. | Contract generation, tests, and future TypeScript generators. |
```

Under `Important Entry Points`, add:

```markdown
- `python -m wf_contract_manifest write|check`: regenerate or verify
  `contracts/workflow-api.manifest.json` from the real composed workflow server.
```

In `docs/current_roadmap.md` under `Recently Completed Platform Milestones`, add a concise completed bullet linking the approved design spec and checked artifact, then state that generated TypeScript inventory/types and representative Effect translation are the next contract-parity slice. Do not claim TypeScript parity is complete.

- [x] **Step 5: Run the complete scoped verification gate**

```powershell
New-Item -ItemType Directory -Force -Path '.pytest-tmp' | Out-Null
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest tests\wf_transport_rpc_http\test_openrpc_contract.py -n 0 --basetemp '.pytest-tmp\manifest-final' -q
.venv\Scripts\python.exe -m wf_contract_manifest check
.venv\Scripts\ruff.exe check src\wf_contract_manifest tests\wf_contract_manifest
.venv\Scripts\basedpyright.exe --level error src\wf_contract_manifest tests\wf_contract_manifest
git diff --check
git status --short
```

Expected:

- all manifest and existing OpenRPC contract tests pass;
- module `check` exits zero without modifying the artifact;
- Ruff, basedpyright, and whitespace checks are clean;
- status contains only files intentionally changed by this plan.

- [x] **Step 6: Run independent two-axis review and fix valid findings**

Dispatch a fresh reviewer that did not implement the slice. Give it:

- the approved design spec;
- this implementation plan;
- the commit range beginning immediately before Task 1; and
- explicit instructions to review both repository standards and spec compliance, prioritizing manifest information loss, false authorization coupling, non-determinism, reference validation gaps, and weak drift tests.

Fix every valid Critical or Important finding and add a regression test for behavioral fixes. Re-run Step 5 after fixes. Record Minor deferrals with rationale in the final report rather than silently ignoring them.

- [x] **Step 7: Archive the completed plan and commit documentation**

Only after all code, tests, review fixes, and verification are complete:

```powershell
Move-Item -LiteralPath 'docs\superpowers\plans\2026-08-01-workflow-contract-manifest.md' -Destination 'docs\historical\superpowers\plans\2026-08-01-workflow-contract-manifest.md'
git add ISSUES.md docs\project_map.md docs\current_roadmap.md docs\superpowers\plans\2026-08-01-workflow-contract-manifest.md docs\historical\superpowers\plans\2026-08-01-workflow-contract-manifest.md tests\wf_contract_manifest\test_committed_manifest.py
git commit -m "docs: record workflow contract manifest"
```

- [x] **Step 8: Remove only the plan-owned temporary pytest directory**

```powershell
$temp = (Resolve-Path '.pytest-tmp').Path
$root = (Resolve-Path '.').Path
if (-not $temp.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to remove pytest temp outside workspace: $temp"
}
Remove-Item -LiteralPath $temp -Recurse -Force
git status --short
```

Expected: the verified workspace-local temporary directory is removed; the worktree is clean after the final commit.

## Completion Criteria

- `contracts/workflow-api.manifest.json` canonically represents all 70 current OpenRPC operations, 126 schema components, and one declared error component.
- Synthetic tests prove ordering, parameter-order preservation, optional/null distinction, title-only stripping, unknown-keyword preservation, all `additionalProperties` states, and empty-schema preservation.
- Invalid envelopes, duplicate/malformed methods, generic success results, external/dangling/unsupported references, and malformed reference values fail with path-bearing `ManifestError` messages.
- Real generation uses the composed in-process server and leaks no local store or transport state.
- `write` changes only the artifact; `check` detects byte drift without mutation.
- The checked-file pytest gate fails on Python/OpenRPC drift.
- No TypeScript runtime, Effect schema, browser allowlist, or presentation behavior changes.
- Current docs identify the manifest as transport inventory, not authorization, and name the next parity slice honestly.
