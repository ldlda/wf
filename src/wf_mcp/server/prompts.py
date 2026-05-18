from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from wf_platform import CapabilitySource, DocumentationPrompt


def register_documentation_prompts(
    server: FastMCP[Any],
    source: CapabilitySource,
) -> None:
    """Project provider-neutral documentation prompts through MCP."""
    for prompt in source.capabilities.prompts.values():
        if not isinstance(prompt, DocumentationPrompt):
            continue
        _register_documentation_prompt(server, prompt)


def _register_documentation_prompt(
    server: FastMCP[Any],
    prompt: DocumentationPrompt,
) -> None:
    """Bind one curated docs guide prompt to its short text."""

    @server.prompt(
        name=prompt.name,
        title=prompt.title,
        description=prompt.description,
    )
    def documentation_prompt() -> str:
        return prompt.text
