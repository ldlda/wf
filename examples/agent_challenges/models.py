from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstructionProfile(StrEnum):
    NONE = "none"
    SKILLS = "skills"
    ALL = "all"
    DEBUG = "debug"


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    root: str = Field(min_length=1)
    module: str = Field(min_length=1)
    registry: str = Field(min_length=1)


class ServerManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: str = Field(min_length=1)
    default_port: int = Field(ge=1, le=65535)


class ReportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_fields: list[str] = Field(default_factory=list)
    success_assertions: dict[str, Any] = Field(default_factory=dict)


class ChallengeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    prompt: str
    workspace_template: str
    source: SourceManifest
    store_root: str
    server: ServerManifest
    report: ReportManifest


class LoadedChallenge(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    manifest_path: Path
    root: Path
    prompt_path: Path
    workspace_template: Path
    source_root: Path
    server_config: Path
    manifest: ChallengeManifest
