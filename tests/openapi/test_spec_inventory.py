from __future__ import annotations

import json
from pathlib import Path

import pytest

from wf_openapi.schemas import input_schema_for_operation, output_schema_for_operation
from wf_openapi.spec import load_openapi_operations

FIXTURE = Path(__file__).parent / "fixtures" / "petstore_minimal.openapi.json"


def test_load_openapi_operations_discovers_operation_ids() -> None:
    operations = load_openapi_operations(FIXTURE)

    names = [operation.name for operation in operations]
    assert names == ["create_pet", "get_pet"]
    assert operations[0].operation_id == "createPet"
    assert operations[0].method == "post"
    assert operations[0].path == "/pets"


def test_load_openapi_operations_uses_deterministic_path_and_method_order(
    tmp_path: Path,
) -> None:
    spec_path = _write_openapi(
        tmp_path,
        {
            "/z-last": {
                "post": {"operationId": "createLast"},
                "get": {"operationId": "getLast"},
            },
            "/a-first": {
                "delete": {"operationId": "deleteFirst"},
                "get": {"operationId": "getFirst"},
                "post": {"operationId": "createFirst"},
            },
        },
    )

    operations = load_openapi_operations(spec_path)

    assert [operation.name for operation in operations] == [
        "get_first",
        "create_first",
        "delete_first",
        "get_last",
        "create_last",
    ]


def test_load_openapi_operations_rejects_duplicate_normalized_operation_names(
    tmp_path: Path,
) -> None:
    spec_path = _write_openapi(
        tmp_path,
        {
            "/pets": {
                "get": {"operationId": "get-pet"},
                "post": {"operationId": "get_pet"},
            },
        },
    )

    with pytest.raises(
        ValueError, match="Duplicate normalized OpenAPI operation name 'get_pet'"
    ):
        load_openapi_operations(spec_path)


@pytest.mark.parametrize(
    ("paths", "message"),
    [
        (
            {"/pets": {"get": {"operationId": "!!!"}}},
            "OpenAPI operationId '!!!' does not produce a usable operation name",
        ),
        (
            {"///": {"get": {}}},
            "OpenAPI fallback operation name for GET /// does not produce a usable operation name",
        ),
    ],
)
def test_load_openapi_operations_rejects_unusable_operation_names(
    tmp_path: Path,
    paths: dict[str, object],
    message: str,
) -> None:
    spec_path = _write_openapi(tmp_path, paths)

    with pytest.raises(ValueError, match=message):
        load_openapi_operations(spec_path)


def test_operation_input_schema_combines_params_and_body() -> None:
    operations = load_openapi_operations(FIXTURE)
    create_pet = operations[0]
    get_pet = operations[1]

    create_schema = input_schema_for_operation(create_pet)
    get_schema = input_schema_for_operation(get_pet)

    assert (
        create_schema["properties"]["body"]["$ref"]
        == "#/components/schemas/CreatePetRequest"
    )
    assert "body" in create_schema["required"]
    assert get_schema["properties"]["path"]["properties"]["petId"]["type"] == "string"
    assert (
        get_schema["properties"]["query"]["properties"]["includeOwner"]["type"]
        == "boolean"
    )
    assert "body" not in get_schema["properties"]


def test_operation_input_schema_emits_parameter_groups_in_canonical_order(
    tmp_path: Path,
) -> None:
    spec_path = _write_openapi(
        tmp_path,
        {
            "/pets/{petId}": {
                "get": {
                    "operationId": "getPet",
                    "parameters": [
                        {
                            "name": "session",
                            "in": "cookie",
                            "schema": {"type": "string"},
                        },
                        {"name": "trace", "in": "header", "schema": {"type": "string"}},
                        {
                            "name": "includeOwner",
                            "in": "query",
                            "schema": {"type": "boolean"},
                        },
                        {
                            "name": "petId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                },
            },
        },
    )
    operation = load_openapi_operations(spec_path)[0]

    schema = input_schema_for_operation(operation)

    assert list(schema["properties"]) == ["path", "query", "header", "cookie"]


def test_operation_effective_parameters_inherit_path_item_and_apply_operation_overrides(
    tmp_path: Path,
) -> None:
    spec_path = _write_openapi(
        tmp_path,
        {
            "/pets": {
                "parameters": [
                    {
                        "name": "locale",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "trace",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "get": {
                    "operationId": "listPets",
                    "parameters": [
                        {
                            "name": "trace",
                            "in": "header",
                            "schema": {"type": "integer"},
                        },
                    ],
                },
            },
        },
    )

    operation = load_openapi_operations(spec_path)[0]
    schema = input_schema_for_operation(operation)

    assert [
        (parameter["name"], parameter["in"])
        for parameter in operation.effective_parameters
    ] == [
        ("locale", "query"),
        ("trace", "header"),
    ]
    assert schema["properties"]["query"]["properties"]["locale"]["type"] == "string"
    assert schema["properties"]["header"]["properties"]["trace"]["type"] == "integer"
    assert schema["properties"]["header"]["required"] == []


def test_operation_records_optional_request_body_for_execution_boundary(
    tmp_path: Path,
) -> None:
    operation = load_openapi_operations(
        _write_openapi(
            tmp_path,
            {
                "/pets": {
                    "post": {
                        "operationId": "createPet",
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                            },
                        },
                    },
                },
            },
        )
    )[0]

    assert operation.has_request_body is True
    assert "body" not in input_schema_for_operation(operation)["required"]


def test_extracted_schemas_are_copied_from_raw_operation() -> None:
    operations = load_openapi_operations(FIXTURE)
    create_pet = operations[0]
    get_pet = operations[1]

    input_schema = input_schema_for_operation(get_pet)
    create_input_schema = input_schema_for_operation(create_pet)
    output_schema = output_schema_for_operation(create_pet)

    input_schema["properties"]["query"]["properties"]["includeOwner"]["type"] = "string"
    create_input_schema["properties"]["body"]["$ref"] = "#/mutated/request"
    output_schema["properties"]["body"]["$ref"] = "#/mutated/response"

    raw_query_schema = get_pet.raw_operation["parameters"][0]["schema"]
    raw_request_schema = create_pet.raw_operation["requestBody"]["content"][
        "application/json"
    ]["schema"]
    raw_response_schema = create_pet.raw_operation["responses"]["201"]["content"][
        "application/json"
    ]["schema"]
    assert raw_query_schema["type"] == "boolean"
    assert raw_request_schema["$ref"] == "#/components/schemas/CreatePetRequest"
    assert raw_response_schema["$ref"] == "#/components/schemas/Pet"

    second_input_schema = input_schema_for_operation(get_pet)
    second_create_input_schema = input_schema_for_operation(create_pet)
    second_output_schema = output_schema_for_operation(create_pet)
    assert (
        second_input_schema["properties"]["query"]["properties"]["includeOwner"]["type"]
        == "boolean"
    )
    assert (
        second_create_input_schema["properties"]["body"]["$ref"]
        == "#/components/schemas/CreatePetRequest"
    )
    assert (
        second_output_schema["properties"]["body"]["$ref"] == "#/components/schemas/Pet"
    )


def test_operation_output_schema_uses_first_success_json_response() -> None:
    operations = load_openapi_operations(FIXTURE)
    schema = output_schema_for_operation(operations[0])

    assert schema["properties"]["status_code"]["type"] == "integer"
    assert schema["properties"]["headers"]["type"] == "object"
    assert schema["properties"]["body"]["$ref"] == "#/components/schemas/Pet"


def test_operation_output_schema_uses_empty_body_when_no_success_json_schema(
    tmp_path: Path,
) -> None:
    spec_path = _write_openapi(
        tmp_path,
        {
            "/pets": {
                "post": {
                    "operationId": "createPet",
                    "responses": {
                        "204": {"description": "No content"},
                        "400": {
                            "description": "Invalid pet",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        },
                    },
                },
            },
        },
    )
    operation = load_openapi_operations(spec_path)[0]

    schema = output_schema_for_operation(operation)

    assert schema["properties"]["body"] == {}


def _write_openapi(tmp_path: Path, paths: dict[str, object]) -> Path:
    """Write the minimum document shape needed by the operation inventory tests."""
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "Test", "version": "1"},
                "paths": paths,
            }
        ),
        encoding="utf-8",
    )
    return spec_path
