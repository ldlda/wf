"""Compatibility shim for workflow API constants.

New code should import these literals from `wf_api.constants`. This module stays
so older MCP workflow-surface imports keep working during extraction.
"""

from wf_api.constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)

__all__ = [
    "DEFAULT_CALL_STEP_ID",
    "DEFAULT_ERROR_OUTCOME",
    "DEFAULT_ERROR_STEP_ID",
    "DEFAULT_OK_OUTCOME",
    "RUNTIME_ERROR_CAPABILITY",
]
