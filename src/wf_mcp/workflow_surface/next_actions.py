"""Compatibility shim for workflow API next-action guidance.

New code should import from `wf_api.next_actions`. This module stays so older
MCP workflow-surface imports keep working during extraction.
"""

from wf_api.next_actions import NextActionPatchExample, NextActionTool, NextActions

__all__ = [
    "NextActionPatchExample",
    "NextActionTool",
    "NextActions",
]
