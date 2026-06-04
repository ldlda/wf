from __future__ import annotations

from typing import Any

from fastapi.datastructures import _Unset
from fastapi_jsonrpc import Params


class _RpcParams(Params):
    def __init__(self, default: Any = ..., **extra: Any) -> None:
        super().__init__(default, example=_Unset, **extra)


def RpcParams(default: Any = ...) -> Any:
    """Bind JSON-RPC method params without fastapi-jsonrpc's warning-prone wrapper.

    ``fastapi_jsonrpc.Params`` currently forwards ``example=Undefined`` into
    FastAPI's ``Body``. FastAPI treats that as the deprecated ``example``
    argument being explicitly provided, so every method registration emits a
    deprecation warning. Keep the upstream subclass so fastapi-jsonrpc still
    recognises method params, but pass FastAPI's real "unset" sentinel.
    """
    return _RpcParams(default)
