from __future__ import annotations


def root_exception(exc: BaseException) -> BaseException:
    current: BaseException = exc
    while isinstance(current, ExceptionGroup) and current.exceptions:
        nested = current.exceptions[0]
        if isinstance(nested, BaseException):
            current = nested
            continue
        break
    return current


def error_payload(exc: BaseException) -> dict[str, str]:
    root = root_exception(exc)
    return {
        "error_type": type(root).__name__,
        "error": str(root),
    }
