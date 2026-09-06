from __future__ import annotations

from typing import Any

from fastapi_jsonrpc import Params


def RpcParams(default: Any = ...) -> Any:
    """Bind JSON-RPC method params with a zero-arg default.

    Upstream fixed the ``example``-sentinel warning in fastapi-jsonrpc 4.0, so
    this is now a plain pass-through. The wrapper stays (in this one file) so
    the ``params: Model = RpcParams()`` call sites keep working: upstream
    ``Params`` still requires ``default`` positionally.
    """
    return Params(default)
