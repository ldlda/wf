"""Docs-backed explanation registry for workflow CLI diagnostics."""

from .models import ExplainCard, ExplainSummary
from .parser import ExplainInputError, extract_explain_codes, parse_explain_input
from .registry import DEFAULT_EXPLAIN_REGISTRY, ExplainRegistry, UnknownExplainCode

__all__ = [
    "DEFAULT_EXPLAIN_REGISTRY",
    "ExplainCard",
    "ExplainInputError",
    "ExplainRegistry",
    "ExplainSummary",
    "UnknownExplainCode",
    "extract_explain_codes",
    "parse_explain_input",
]
