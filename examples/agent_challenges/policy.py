from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .metrics import ToolCallEvidence
from .models import InstructionProfile


class EvaluationValidity(StrEnum):
    CLEAN = "clean"
    CONTAMINATED = "contaminated"
    UNAUDITABLE = "unauditable"


class PolicyCoverage(StrEnum):
    """How much of the recorded evidence the automatic policy pass can inspect."""

    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class PolicyEvidence:
    validity: EvaluationValidity
    coverage: PolicyCoverage
    disallowed_reads: tuple[str, ...]
    escalated_to_product_code: bool
    opaque_shell_commands: tuple[str, ...]
    reads_by_category: dict[str, tuple[str, ...]]


SOLUTION_FILE_NAMES = {
    "final-report.md",
    "workflow.plan.json",
}
SOLUTION_FILE_SUFFIXES = (
    ".plan.json",
    ".report.json",
    ".report.md",
)
SOLUTION_FILE_PREFIXES = ("patch",)


def _looks_like_solution_artifact(path: Path) -> bool:
    """Return true for prior-trial files likely to contain a full answer."""
    name = path.name
    return (
        name in SOLUTION_FILE_NAMES
        or name.endswith(SOLUTION_FILE_SUFFIXES)
        or any(
            name.startswith(prefix) and name.endswith(".json")
            for prefix in SOLUTION_FILE_PREFIXES
        )
    )


def _classify_path(
    path_str: str,
    *,
    workspace_root: str,
    repository_root: str,
    workspaces_root: str,
) -> str:
    if path_str.startswith(".agent/skills/"):
        return "supplied_skills"

    # OpenCode glob/grep evidence may contain only a search pattern, not the
    # concrete matched files. Treat broad patterns as search intent so they
    # produce follow-up notes without pretending a forbidden file was read.
    if any(marker in path_str for marker in ("*", "?")):
        return "search_intent"

    try:
        raw_path = Path(path_str)
        p = (
            raw_path.resolve()
            if raw_path.is_absolute()
            else (Path(workspace_root) / raw_path).resolve()
        )
    except OSError, ValueError:
        return "unknown"

    workspace = Path(workspace_root).resolve()
    repository = Path(repository_root).resolve()
    workspaces = Path(workspaces_root).resolve()

    if p.is_relative_to(workspace):
        rel = p.relative_to(workspace)
        if rel.parts and rel.parts[0] == ".agent":
            return "supplied_skills"
        if rel.parts and rel.parts[0].startswith(".wf"):
            return "prior_store"
        return "workspace"

    if p.is_relative_to(workspaces):
        if _looks_like_solution_artifact(p):
            return "existing_solution"
        return "adjacent_attempts"

    if p.is_relative_to(repository):
        rel = p.relative_to(repository)
        parts = rel.parts
        if not parts:
            return "repository_index"
        if parts and parts[0] == ".wf_store":
            return "prior_store"
        if parts and parts[0] in (".agent", "skills"):
            return "supplied_skills"
        if parts and parts[0] == "tests":
            return "tests"
        if parts and parts[0] == "src":
            return "source"
        if parts and parts[0] == "docs":
            return "docs"
        if parts and parts[0] == "examples":
            if parts[-1:] == ("workflow.plan.json",):
                return "existing_solution"
            if parts[-1:] == ("ops.py",):
                return "example_implementation"
            return "examples"
        return "source"

    return "outside"


def _extract_paths_from_tool_call(
    tc: ToolCallEvidence,
) -> list[str]:
    tool_name = tc.tool.lower()
    if tool_name in ("read", "glob", "grep", "list", "search"):
        path_val = (
            tc.input.get("path")
            or tc.input.get("file")
            or tc.input.get("filePath")
            or tc.input.get("pattern")
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


def _is_auditable_product_command(command: str) -> bool:
    """Recognize direct workflow CLI calls without blessing arbitrary shell."""
    return (
        re.match(
            r"^(?:uv\s+run(?:\s+--env-file\s+\S+)?\s+)?wf(?:\s|$)",
            command.strip(),
            flags=re.IGNORECASE,
        )
        is not None
    )


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
    allowed_skills_categories = {
        "repository_index",
        "workspace",
        "supplied_skills",
        "search_intent",
        "unknown",
    }

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

            if category == "existing_solution":
                disallowed_reads.append(path_str)
            elif profile == InstructionProfile.NONE:
                if category not in ("workspace", "search_intent", "unknown"):
                    disallowed_reads.append(path_str)
            elif profile == InstructionProfile.SKILLS:
                if category not in allowed_skills_categories:
                    disallowed_reads.append(path_str)
            elif profile in (InstructionProfile.ALL, InstructionProfile.DEBUG):
                if category in (
                    "source",
                    "tests",
                    "docs",
                    "examples",
                    "example_implementation",
                ):
                    escalated_to_product_code = True

            if category == "example_implementation":
                escalated_to_product_code = True

        shell_cmd = _extract_shell_command(tc)
        if shell_cmd is not None and not _is_auditable_product_command(shell_cmd):
            opaque_shell_commands.append(shell_cmd)

    # Validity is about observed rule violations. Opaque shell commands reduce
    # automatic coverage, but they are not violations by themselves: the manual
    # audit layer is responsible for reviewing those command bodies.
    validity = (
        EvaluationValidity.CONTAMINATED
        if disallowed_reads
        else EvaluationValidity.CLEAN
    )
    coverage = (
        PolicyCoverage.PARTIAL if opaque_shell_commands else PolicyCoverage.COMPLETE
    )

    frozen_reads_by_category = {k: tuple(v) for k, v in reads_by_category.items()}

    return PolicyEvidence(
        validity=validity,
        coverage=coverage,
        disallowed_reads=tuple(disallowed_reads),
        escalated_to_product_code=escalated_to_product_code,
        opaque_shell_commands=tuple(opaque_shell_commands),
        reads_by_category=frozen_reads_by_category,
    )
