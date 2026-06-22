from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .models import InstructionProfile, LoadedChallenge

_PROMPT_DIR = Path(__file__).resolve().parent
_BASE_PROMPT = _PROMPT_DIR / "base-prompt.md"
_PROFILE_DIR = _PROMPT_DIR / "profile-prompts"

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    text: str
    base_sha256: str
    profile_sha256: str
    challenge_sha256: str
    rendered_sha256: str


def _load_profile_fragment(profile: InstructionProfile) -> str:
    path = _PROFILE_DIR / f"{profile.value}.md"
    return path.read_text(encoding="utf-8")


def _resolve_placeholders(template: str, *, variables: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise ValueError(f"unresolved placeholder {{{{{key}}}}}")
        return variables[key]

    return _PLACEHOLDER_RE.sub(_replace, template)


def compose_trial_prompt(
    challenge: LoadedChallenge,
    *,
    profile: InstructionProfile,
    wf_command_prefix: str,
    server_context: str,
    workspace_path: Path,
) -> RenderedPrompt:
    base_text = _BASE_PROMPT.read_text(encoding="utf-8")
    profile_text = _load_profile_fragment(profile)
    challenge_text = challenge.prompt_path.read_text(encoding="utf-8")

    rendered = _resolve_placeholders(
        base_text,
        variables={
            "wf_command_prefix": wf_command_prefix,
            "server_context": server_context,
            "workspace_path": str(workspace_path),
        },
    )

    return RenderedPrompt(
        text=f"{rendered}\n{profile_text}\n{challenge_text}",
        base_sha256=_sha256(base_text),
        profile_sha256=_sha256(profile_text),
        challenge_sha256=_sha256(challenge_text),
        rendered_sha256=_sha256(f"{rendered}\n{profile_text}\n{challenge_text}"),
    )
