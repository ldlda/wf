from __future__ import annotations

from wf_openapi.executor import OpenApiExecutionConfig


def test_openapi_runtime_does_not_require_generated_manifest() -> None:
    config = OpenApiExecutionConfig(base_url="https://api.example.test")

    assert config.base_url == "https://api.example.test"
    assert not hasattr(config, "generated_package")
    assert not hasattr(config, "operation_modules")
    assert not hasattr(config, "parameter_arguments")
