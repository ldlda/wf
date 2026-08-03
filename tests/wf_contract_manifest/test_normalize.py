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
    assert manifest["operations"][0]["namespace"] == ["workflow", "alpha"]
    assert manifest["operations"][0]["action"] == "inspect"
    assert manifest["operations"][1]["namespace"] == ["workflow", "zeta"]
    assert manifest["operations"][1]["action"] == "run"
    assert manifest["operations"][0]["result"] == {
        "schema": {"$ref": "#/components/schemas/AlphaResult"}
    }
    assert manifest["operations"][0]["errors"] == [
        {"$ref": "#/components/errors/5000"}
    ]
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
