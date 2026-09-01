from __future__ import annotations

from typing import Any

import pytest


class FakeWorkflowClient:
    """Small configurable adapter used to test rich clients without HTTP."""

    def __init__(self, **responses: object) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def response(self, method: str) -> object:
        return self.responses[method]

    def _response(self, method: str, params: dict[str, Any]) -> object:
        self.calls.append((method, params))
        return self.response(method)

    async def list_capabilities(self, **params: Any) -> object:
        return self._response("workflow.capabilities.list", params)

    async def inspect_capability(self, **params: Any) -> object:
        return self._response("workflow.capabilities.inspect", params)

    async def call_capability(self, **params: Any) -> object:
        return self._response("workflow.capabilities.call", params)

    async def inspect_artifact(self, **params: Any) -> object:
        return self._response("workflow.artifacts.inspect", params)

    async def list_artifacts(self, **params: Any) -> object:
        return self._response("workflow.artifacts.list", params)

    async def save_artifact(self, artifact: dict[str, Any]) -> object:
        return self._response("workflow.artifacts.save", {"artifact": artifact})

    async def validate_artifact_plan(self, **params: Any) -> object:
        return self._response("workflow.artifacts.validate_plan", params)

    async def create_artifact_from_plan(self, **params: Any) -> object:
        return self._response("workflow.artifacts.create_from_plan", params)

    async def list_deployments(self) -> object:
        return self._response("workflow.deployments.list", {})

    async def inspect_deployment(self, **params: Any) -> object:
        return self._response("workflow.deployments.inspect", params)

    async def save_deployment(self, deployment: dict[str, Any]) -> object:
        return self._response("workflow.deployments.save", {"deployment": deployment})

    async def validate_deployment(self, **params: Any) -> object:
        return self._response("workflow.deployments.validate", params)

    async def run_deployment(self, **params: Any) -> object:
        return self._response("workflow.runs.start", params)

    async def list_runs(self, **params: Any) -> object:
        return self._response("workflow.runs.list", params)

    async def inspect_run(self, **params: Any) -> object:
        return self._response("workflow.runs.inspect", params)

    async def resume_run(self, **params: Any) -> object:
        return self._response("workflow.runs.resume", params)

    async def read_run_trace(self, **params: Any) -> object:
        return self._response("workflow.runs.trace", params)

    async def _call(self, method: str, params: dict[str, Any]) -> object:
        return self._response(method, params)


@pytest.fixture
def fake_client() -> FakeWorkflowClient:
    return FakeWorkflowClient()
