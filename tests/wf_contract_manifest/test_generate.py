from __future__ import annotations

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


def test_generates_the_complete_real_workflow_contract() -> None:
    manifest = generate_manifest()
    schemas = manifest["components"]["schemas"]

    assert len(manifest["operations"]) == 70
    assert len({operation["method"] for operation in manifest["operations"]}) == 70
    assert len(schemas) == 126
    assert len(manifest["components"]["errors"]) == 1
    assert all(
        set(operation["result"]["schema"]) == {"$ref"}
        for operation in manifest["operations"]
    )
    assert {name for name in UNION_RESULTS if "anyOf" in schemas[name]} == UNION_RESULTS


def test_generated_contract_preserves_security_and_extension_boundaries() -> None:
    schemas = generate_manifest()["components"]["schemas"]

    assert AUTH_SECURITY_COMPONENTS <= schemas.keys()
    for name in AUTH_SECURITY_COMPONENTS:
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
