from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Protocol

import pytest

from wf_contract_manifest import ManifestError, manifest_from_openrpc

from .fixtures import synthetic_openrpc_document


class DocumentMutation(Protocol):
    def __call__(self, document: dict[str, Any]) -> object: ...


def assert_manifest_error(document: dict[str, Any], path: str, message: str) -> None:
    with pytest.raises(ManifestError) as error_info:
        manifest_from_openrpc(document)

    assert error_info.value.path == path
    assert error_info.value.message == message
    assert str(error_info.value) == f"{path}: {message}"


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
    assert manifest["operations"][0]["namespace"] == ["workflow", "alpha"]
    assert manifest["operations"][0]["action"] == "inspect"
    assert manifest["operations"][1]["namespace"] == ["workflow", "zeta"]
    assert manifest["operations"][1]["action"] == "run"
    assert manifest["operations"][0]["result"] == {
        "schema": {"$ref": "#/components/schemas/AlphaResult"}
    }
    assert manifest["operations"][0]["errors"] == [{"$ref": "#/components/errors/5000"}]
    assert list(manifest["components"]["schemas"]) == [
        "AlphaResult",
        "FreeJson",
        "ZetaResult",
    ]
    assert list(manifest["components"]["errors"]) == ["5000"]
    assert manifest["components"]["errors"]["5000"] == {
        "code": 5000,
        "message": "Workflow operation failed",
        "data": {"type": "object", "additionalProperties": False},
    }


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


def test_defaults_an_absent_parameter_required_flag_to_false() -> None:
    document = synthetic_openrpc_document()
    del document["methods"][1]["params"][0]["required"]

    operation = manifest_from_openrpc(document)["operations"][0]

    assert operation["params"][0]["required"] is False


def test_removes_only_titles_and_preserves_unknown_schema_keywords() -> None:
    manifest = manifest_from_openrpc(synthetic_openrpc_document())
    optional_schema = manifest["operations"][0]["params"][0]["schema"]

    assert "title" not in optional_schema
    assert optional_schema["x-future-keyword"] == {
        "title": "removed recursively",
        "value": 1,
    }
    assert manifest["components"]["schemas"]["FreeJson"] == {}
    assert manifest["components"]["schemas"]["ZetaResult"]["properties"] == {
        "extension": {"additionalProperties": True}
    }


def test_preserves_named_title_entries_in_schema_maps() -> None:
    alpha = manifest_from_openrpc(synthetic_openrpc_document())["components"][
        "schemas"
    ]["AlphaResult"]

    assert alpha["required"] == ["mode", "payload", "title"]
    properties = alpha["properties"]
    definitions = alpha["$defs"]
    assert isinstance(properties, dict)
    assert isinstance(definitions, dict)
    assert properties["title"] == {"type": "string"}
    assert definitions["title"] == {"type": "string"}


def test_preserves_conditional_schema_keywords() -> None:
    alpha = manifest_from_openrpc(synthetic_openrpc_document())["components"][
        "schemas"
    ]["AlphaResult"]

    assert alpha["if"] == {"properties": {"mode": {"const": "alpha"}}}
    assert alpha["then"] == {"required": ["payload"]}
    assert alpha["not"] == {"required": ["forbidden"]}


@pytest.mark.parametrize(
    ("field", "value", "missing", "path", "message"),
    [
        ("openrpc", None, True, "$.openrpc", "expected a non-empty string"),
        ("openrpc", 1.2, False, "$.openrpc", "expected a non-empty string"),
        ("methods", None, True, "$.methods", "expected an array"),
        ("methods", {}, False, "$.methods", "expected an array"),
        ("components", None, True, "$.components", "expected an object"),
        ("components", [], False, "$.components", "expected an object"),
        (
            "schemas",
            None,
            True,
            "$.components.schemas",
            "expected an object",
        ),
        (
            "schemas",
            [],
            False,
            "$.components.schemas",
            "expected an object",
        ),
        (
            "errors",
            None,
            True,
            "$.components.errors",
            "expected an object",
        ),
        ("errors", [], False, "$.components.errors", "expected an object"),
    ],
)
def test_rejects_invalid_or_missing_top_level_envelope_values(
    field: str,
    value: object,
    missing: bool,
    path: str,
    message: str,
) -> None:
    document = synthetic_openrpc_document()
    if field in {"schemas", "errors"}:
        components = document["components"]
        if missing:
            components.pop(field)
        else:
            components[field] = value
    elif missing:
        document.pop(field)
    else:
        document[field] = value

    assert_manifest_error(document, path, message)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "expected a non-empty string"),
        ("workflow", "malformed dotted method name"),
        (
            "workflow..run",
            "malformed dotted method name",
        ),
        (
            ".workflow.run",
            "malformed dotted method name",
        ),
        (
            "workflow.run.",
            "malformed dotted method name",
        ),
    ],
)
def test_rejects_empty_or_malformed_dotted_method_names(
    name: str, message: str
) -> None:
    document = synthetic_openrpc_document()
    document["methods"][0]["name"] = name

    assert_manifest_error(document, "$.methods[0].name", message)


@pytest.mark.parametrize(
    ("field", "value", "missing", "message"),
    [
        ("required", "yes", False, "expected a boolean"),
        ("schema", [], False, "expected a schema object"),
        ("schema", None, True, "expected a schema object"),
    ],
)
def test_rejects_invalid_or_missing_parameter_fields(
    field: str, value: object, missing: bool, message: str
) -> None:
    document = synthetic_openrpc_document()
    parameter = document["methods"][1]["params"][0]
    if missing:
        parameter.pop(field)
    else:
        parameter[field] = value

    assert_manifest_error(
        document,
        f"$.methods[1].params[0].{field}",
        message,
    )


def test_rejects_invalid_result_schema_shape() -> None:
    document = synthetic_openrpc_document()
    document["methods"][1]["result"]["schema"] = []

    assert_manifest_error(
        document,
        "$.methods[1].result.schema",
        "success result must reference a named schema component",
    )


def test_reports_a_missing_success_result_schema() -> None:
    document = synthetic_openrpc_document()
    del document["methods"][1]["result"]["schema"]

    assert_manifest_error(
        document,
        "$.methods[1].result.schema",
        "missing success result schema",
    )


def test_rejects_extra_raw_success_result_schema_keys() -> None:
    document = synthetic_openrpc_document()
    document["methods"][0]["result"]["schema"]["title"] = "extra"

    assert_manifest_error(
        document,
        "$.methods[0].result.schema",
        "success result must reference a named schema component",
    )


def test_rejects_invalid_method_error_schema_shape() -> None:
    document = synthetic_openrpc_document()
    document["methods"][1]["errors"][0] = []

    assert_manifest_error(
        document,
        "$.methods[1].errors[0]",
        "expected a schema object",
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_schema_numbers_with_exact_path(value: float) -> None:
    document = synthetic_openrpc_document()
    document["components"]["schemas"]["AlphaResult"]["properties"]["mode"]["const"] = (
        value
    )

    assert_manifest_error(
        document,
        "$.components.schemas.AlphaResult.properties.mode.const",
        "expected a finite JSON number",
    )


@pytest.mark.parametrize(
    ("namespace", "path"),
    [
        ("schemas", "$.components.schemas"),
        ("errors", "$.components.errors"),
    ],
)
def test_rejects_non_string_component_keys_before_sorting(
    namespace: str, path: str
) -> None:
    document = synthetic_openrpc_document()
    document["components"][namespace][1] = {}

    assert_manifest_error(document, path, "expected string object keys")


@pytest.mark.parametrize(
    ("mutate", "path", "message"),
    [
        (
            lambda document: document.update({"openrpc": "2.0.0"}),
            "$.openrpc",
            "unsupported OpenRPC version '2.0.0'; expected '1.2.6'",
        ),
        (
            lambda document: document.update({"methods": {}}),
            "$.methods",
            "expected an array",
        ),
        (
            lambda document: document["methods"].append(
                deepcopy(document["methods"][0])
            ),
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
            "missing success result schema",
        ),
        (
            lambda document: document["methods"][0]["result"].update(
                {
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                    }
                }
            ),
            "$.methods[0].result.schema",
            "success result must reference a named schema component",
        ),
    ],
)
def test_rejects_malformed_openrpc_contracts(
    mutate: DocumentMutation, path: str, message: str
) -> None:
    document = synthetic_openrpc_document()
    mutate(document)

    assert_manifest_error(document, path, message)


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("https://example.test/schema.json", "external references are not supported"),
        ("#/definitions/Result", "unsupported local reference namespace"),
        (
            "#/components/parameters/Value",
            "unsupported component reference namespace",
        ),
        ("#/components/schemas/Missing", "dangling local reference"),
        (
            "#/components/schemas/A~0B",
            "unsupported escaped component reference",
        ),
    ],
)
def test_rejects_unsupported_or_dangling_references(
    reference: str, message: str
) -> None:
    document = synthetic_openrpc_document()
    document["components"]["schemas"]["AlphaResult"]["properties"]["linked"] = {
        "$ref": reference
    }

    with pytest.raises(ManifestError) as exc_info:
        manifest_from_openrpc(document)

    assert exc_info.value.path.endswith(".properties.linked.$ref")
    assert exc_info.value.message == message


def test_reports_reference_errors_at_original_method_path() -> None:
    document = synthetic_openrpc_document()
    assert [method["name"] for method in document["methods"]] == [
        "workflow.zeta.run",
        "workflow.alpha.inspect",
    ]
    document["methods"][0]["errors"][0] = {"$ref": "#/components/errors/Missing"}

    with pytest.raises(ManifestError) as exc_info:
        manifest_from_openrpc(document)

    assert exc_info.value.path == "$.methods[0].errors[0].$ref"
    assert exc_info.value.message == "dangling local reference"


def test_accepts_nested_schema_and_error_component_references() -> None:
    document = synthetic_openrpc_document()
    document["components"]["schemas"]["AlphaResult"]["properties"]["linked"] = {
        "$ref": "#/components/schemas/ZetaResult"
    }

    manifest = manifest_from_openrpc(document)

    assert manifest["operations"][0]["errors"] == [{"$ref": "#/components/errors/5000"}]
