from wf_contract_manifest import (
    DEFAULT_MANIFEST_PATH,
    check_manifest,
    generate_manifest,
)


def test_committed_manifest_matches_the_python_workflow_contract() -> None:
    check_manifest(generate_manifest(), DEFAULT_MANIFEST_PATH)
