"""Shared workflow-surface literals used by generated draft helpers."""

DEFAULT_CALL_STEP_ID = "call"
DEFAULT_ERROR_STEP_ID = "tool_error"
DEFAULT_OK_OUTCOME = "ok"
DEFAULT_ERROR_OUTCOME = "error"
RUNTIME_ERROR_CAPABILITY = "wf.std.runtime_error"

__all__ = [
    "DEFAULT_CALL_STEP_ID",
    "DEFAULT_ERROR_OUTCOME",
    "DEFAULT_ERROR_STEP_ID",
    "DEFAULT_OK_OUTCOME",
    "RUNTIME_ERROR_CAPABILITY",
]
