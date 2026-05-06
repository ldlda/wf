from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

OutputT_co = TypeVar("OutputT_co", bound=BaseModel, covariant=True)


@dataclass(frozen=True, slots=True)
class NodeReturn(Generic[OutputT_co]):
    outcome: str
    output: OutputT_co
