from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .metrics import ToolCallEvidence
from .models import InstructionProfile


class EvaluationValidity(StrEnum):
    CLEAN = "clean"
    CONTAMINATED = "contaminated"
    UNAUDITABLE = "unauditable"


@dataclass(frozen=True, slots=True)
class PolicyEvidence:
    validity: EvaluationValidity
    disallowed_reads: tuple[str, ...]
    escalated_to_product_code: bool
    opaque_shell_commands: tuple[str, ...]
    reads_by_category: dict[str, tuple[str, ...]]


def _classify_path(
    path_str: str,
    *,
    workspace_root: str,
    repository_root: str,
    workspaces_root: str,
) -> str:
    try:
        p = Path(path_str).resolve()
    except OSError, ValueError:
        return "unknown"

    workspace = Path(workspace_root).resolve()
    repository = Path(repository_root).resolve()
    workspaces = Path(workspaces_root).resolve()

    if p.is_relative_to(workspace):
        rel = p.relative_to(workspace)
        if rel.parts and rel.parts[0] == ".agent":
            return "supplied_skills"
        return "workspace"

    if p.is_relative_to(workspaces):
        return "adjacent_attempts"

    if p.is_relative_to(repository):
        rel = p.relative_to(repository)
        parts = rel.parts
        if parts and parts[0] == ".wf_store":
            return "prior_store"
        if parts and parts[0] == "tests":
            return "tests"
        if parts and parts[0] == "src":
            return "source"
        if parts and parts[0] == "docs":
            return "docs"
        if parts and parts[0] == "examples":
            return "examples"
        return "source"

    return "outside"


def _extract_paths_from_tool_call(
    tc: ToolCallEvidence,
) -> list[str]:
    tool_name = tc.tool.lower()
    if tool_name in ("read", "glob", "grep", "list", "search"):
        path_val = (
            tc.input.get("path") or tc.input.get("file") or tc.input.get("pattern")
        )
        if isinstance(path_val, str) and path_val:
            return [path_val]
    return []


def _extract_shell_command(tc: ToolCallEvidence) -> str | None:
    if tc.tool.lower() in ("bash", "shell", "exec", "run"):
        cmd = tc.input.get("command") or tc.input.get("cmd")
        if isinstance(cmd, str) and cmd:
            return cmd
    return None


def evaluate_policy(
    profile: InstructionProfile | str,
    tool_calls: list[ToolCallEvidence],
    *,
    workspace_root: str | Path,
    repository_root: str | Path,
    workspaces_root: str | Path,
) -> PolicyEvidence:
    if isinstance(profile, str):
        profile = InstructionProfile(profile)
    workspace_root_str = str(workspace_root)
    repository_root_str = str(repository_root)
    workspaces_root_str = str(workspaces_root)

    disallowed_reads: list[str] = []
    opaque_shell_commands: list[str] = []
    reads_by_category: dict[str, list[str]] = {}
    escalated_to_product_code = False

    for tc in tool_calls:
        paths = _extract_paths_from_tool_call(tc)
        for path_str in paths:
            category = _classify_path(
                path_str,
                workspace_root=workspace_root_str,
                repository_root=repository_root_str,
                workspaces_root=workspaces_root_str,
            )
            reads_by_category.setdefault(category, []).append(path_str)

            if profile == InstructionProfile.NONE:
                if category not in ("workspace", "unknown"):
                    disallowed_reads.append(path_str)
            elif profile == InstructionProfile.SKILLS:
                if category not in ("workspace", "supplied_skills", "unknown"):
                    disallowed_reads.append(path_str)
            elif profile == InstructionProfile.ALL:
                if category in ("source", "tests", "docs", "examples"):
                    escalated_to_product_code = True

        shell_cmd = _extract_shell_command(tc)
        if shell_cmd is not None:
            opaque_shell_commands.append(shell_cmd)

    if disallowed_reads:
        validity = EvaluationValidity.CONTAMINATED
    elif opaque_shell_commands and not disallowed_reads:
        validity = EvaluationValidity.UNAUDITABLE
    else:
        validity = EvaluationValidity.CLEAN

    frozen_reads_by_category = {k: tuple(v) for k, v in reads_by_category.items()}

    return PolicyEvidence(
        validity=validity,
        disallowed_reads=tuple(disallowed_reads),
        escalated_to_product_code=escalated_to_product_code,
        opaque_shell_commands=tuple(opaque_shell_commands),
        reads_by_category=frozen_reads_by_category,
    )
