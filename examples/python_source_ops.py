from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import node


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    """Return the submitted text through a project-local Python source."""
    return EchoOutput(echoed=payload.text)


@node(name="authoring.upper")
def upper(payload: EchoInput) -> EchoOutput:
    """Upper-case text while exercising authoring-name qualification."""
    return EchoOutput(echoed=payload.text.upper())


registry = [echo, upper]
