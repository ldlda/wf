from __future__ import annotations

from typing import NoReturn

import fastapi_jsonrpc as jsonrpc
from pydantic import BaseModel, ConfigDict


class WorkflowRpcError(jsonrpc.BaseError):
    """Expected workflow application error surfaced through JSON-RPC."""

    CODE = 5000
    MESSAGE = "Workflow operation failed"

    class DataModel(BaseModel):
        code: str
        message: str

        model_config = ConfigDict(extra="forbid")


def raise_workflow_rpc_error(exc: Exception) -> NoReturn:
    """Map expected application exceptions without swallowing programming bugs."""

    raise WorkflowRpcError(
        data={
            "code": exc.__class__.__name__,
            "message": str(exc),
        }
    ) from exc
