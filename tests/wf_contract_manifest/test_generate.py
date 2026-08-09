from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from wf_contract_manifest import generate_manifest

UNION_RESULTS = {
    "InspectCapabilityResult",
    "PatchDraftResult",
    "ValidateDraftResult",
    "CompileDraftWorkspaceResult",
    "CreateArtifactFromWorkspaceResult",
}

AUTH_SECURITY_COMPONENTS = {
    "AuthRecordSummaryPayload",
    "ListAuthRecordsResult",
    "DeleteAuthRecordResult",
    "SourceAuthDiagnosisPayload",
    "SourceDiagnosisResult",
}

AUTH_METHODS = {
    "workflow.admin.auth.delete",
    "workflow.admin.auth.inspect",
    "workflow.admin.auth.list",
    "workflow.admin.auth.save",
}


def _schema_references(value: Any) -> Iterator[str]:
    if isinstance(value, Mapping):
        reference = value.get("$ref")
        if isinstance(reference, str):
            yield reference
        for child in value.values():
            yield from _schema_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _schema_references(child)


def _reachable_schema_names(schemas: Mapping[str, Any], roots: set[str]) -> set[str]:
    """Return schema components reachable through local schema references."""
    reachable: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        prefix = "#/components/schemas/"
        for reference in _schema_references(schemas[name]):
            if reference.startswith(prefix):
                pending.append(reference.removeprefix(prefix))
    return reachable


def _structured_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _structured_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _structured_strings(child)


def _schema_objects(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _schema_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _schema_objects(child)


def _result_component_name(operation: Any) -> str:
    reference = operation["result"]["schema"]["$ref"]
    assert isinstance(reference, str)
    return reference.removeprefix("#/components/schemas/")


def test_generates_the_complete_real_workflow_contract() -> None:
    manifest = generate_manifest()
    schemas = manifest["components"]["schemas"]

    assert len(manifest["operations"]) == 70
    assert len({operation["method"] for operation in manifest["operations"]}) == 70
    assert len(schemas) == 127
    assert len(manifest["components"]["errors"]) == 1
    assert all(
        set(operation["result"]["schema"]) == {"$ref"}
        for operation in manifest["operations"]
    )
    assert {name for name in UNION_RESULTS if "anyOf" in schemas[name]} == UNION_RESULTS


def test_manifest_preserves_recursive_json_value_binding_contract() -> None:
    schemas: dict[str, Any] = generate_manifest()["components"]["schemas"]
    value_schema = schemas["InputValueBinding"]["properties"]["value"]

    assert value_schema["$ref"] == "#/components/schemas/JsonValue"
    json_value_schema = schemas["JsonValue"]
    assert {branch["type"] for branch in json_value_schema["anyOf"]} == {
        "boolean",
        "integer",
        "number",
        "string",
        "array",
        "object",
        "null",
    }
    assert json_value_schema["anyOf"][4]["items"] == {
        "$ref": "#/components/schemas/JsonValue"
    }
    assert json_value_schema["anyOf"][5]["additionalProperties"] == {
        "$ref": "#/components/schemas/JsonValue"
    }


def test_manifest_contains_the_two_focused_step_binding_operations() -> None:
    methods = {operation["method"] for operation in generate_manifest()["operations"]}

    assert {
        "workflow.draft_workspaces.set_step_input_bindings",
        "workflow.draft_workspaces.set_step_output_bindings",
    } <= methods


def test_generated_contract_preserves_security_and_extension_boundaries() -> None:
    manifest = generate_manifest()
    schemas = manifest["components"]["schemas"]

    assert AUTH_SECURITY_COMPONENTS <= schemas.keys()
    for name in AUTH_SECURITY_COMPONENTS:
        properties = schemas[name].get("properties", {})
        assert isinstance(properties, dict)
        assert "payload" not in properties

    result_components = {
        _result_component_name(operation)
        for operation in manifest["operations"]
        if operation["method"] in AUTH_METHODS
    }
    assert {
        operation["method"] for operation in manifest["operations"]
    } & AUTH_METHODS == AUTH_METHODS
    reachable = _reachable_schema_names(schemas, result_components)
    for name in reachable:
        for schema in _schema_objects(schemas[name]):
            properties = schema.get("properties", {})
            if isinstance(properties, Mapping):
                assert "payload" not in properties, name

    assert schemas["SourceDiagnosisResult"]["additionalProperties"] is True
    assert schemas["RegistryEntryPayload"]["additionalProperties"] is True


def test_generated_contract_contains_no_temporary_or_transport_state() -> None:
    strings = set(_structured_strings(generate_manifest()))

    assert not any("TemporaryDirectory" in value for value in strings)
    assert not any("\\Temp\\" in value for value in strings)
    assert not any("127.0.0.1" in value for value in strings)
    assert not any("/rpc" in value for value in strings)


def test_generated_required_properties_are_declared() -> None:
    schemas = generate_manifest()["components"]["schemas"]

    for component_name, component in schemas.items():
        for schema in _schema_objects(component):
            required = schema.get("required")
            properties = schema.get("properties")
            if isinstance(required, list) and isinstance(properties, Mapping):
                assert set(required) <= properties.keys(), component_name
