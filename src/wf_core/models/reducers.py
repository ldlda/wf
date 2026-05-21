from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_platform.refs import CapabilityRef


def _raise_conflicting_ref_and_name() -> None:
    """Reject ambiguous reducer references before compatibility coercion."""
    raise ValueError("reducer ref and name are mutually exclusive")


class ReducerRef(BaseModel):
    """Reference to one reducer capability plus JSON-compatible configuration."""

    ref: CapabilityRef
    config: dict[str, Any] = Field(default_factory=dict)

    def __init__(
        self,
        *,
        ref: CapabilityRef | str | Mapping[str, Any] | None = None,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        **extra: object,
    ) -> None:
        """Accept legacy `name=` construction while storing canonical `ref`.

        Existing authoring and runtime code still constructs reducers with
        `ReducerRef(name="wf.std.add")`. That remains source-compatible, but
        the model state is now the structural capability reference.
        """
        if ref is not None and name is not None:
            _raise_conflicting_ref_and_name()
        payload: dict[str, object] = {"config": config or {}}
        if ref is not None:
            payload["ref"] = ref
        if name is not None:
            payload["name"] = name
        payload.update(extra)
        super().__init__(**payload)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_shapes(cls, value: object) -> object:
        """Accept old reducer strings/`name` objects as parse-only shorthand."""
        if isinstance(value, str):
            return {"ref": CapabilityRef.parse(value)}
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "ref" in data and "name" in data:
            _raise_conflicting_ref_and_name()
        if "ref" not in data and "name" in data:
            data["ref"] = CapabilityRef.parse(str(data.pop("name")))
        return data

    @property
    def name(self) -> str:
        """Display/registry compatibility key for existing reducer catalogs."""
        return str(self.ref)


class ReducerSpec(BaseModel):
    """Inspectable metadata for one named pure state reducer."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    config_schema: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    )
