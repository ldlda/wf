from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from wf_authoring import node

_EXAMPLE_DIR = Path(__file__).resolve().parent
_DOCUMENT_DIR = _EXAMPLE_DIR / "documents"


class ListDocumentsInput(BaseModel):
    include_archived: bool = Field(
        default=False,
        description="Reserved for future filtering; current fixture has no archived docs.",
    )


class DocumentRef(BaseModel):
    name: str
    title: str


class ListDocumentsOutput(BaseModel):
    documents: list[DocumentRef]


class ReadDocumentsInput(BaseModel):
    names: list[str] = Field(description="Document names returned by list_documents.")


class DocumentText(BaseModel):
    name: str
    title: str
    text: str


class ReadDocumentsOutput(BaseModel):
    documents: list[DocumentText]


@node(
    name="list_documents",
    description="List deterministic lda.chat project documents available to the demo.",
)
def list_documents(payload: ListDocumentsInput) -> ListDocumentsOutput:
    return _list_documents(payload)


@node(
    name="read_documents",
    description="Read selected lda.chat project documents by fixture name.",
)
def read_documents(payload: ReadDocumentsInput) -> ReadDocumentsOutput:
    return _read_documents(payload)


def _list_documents(_payload: ListDocumentsInput) -> ListDocumentsOutput:
    documents = [
        DocumentRef(name=path.name, title=_title_for(path))
        for path in sorted(_DOCUMENT_DIR.glob("*.md"))
    ]
    return ListDocumentsOutput(documents=documents)


def _read_documents(payload: ReadDocumentsInput) -> ReadDocumentsOutput:
    allowed = {
        document.name for document in _list_documents(ListDocumentsInput()).documents
    }
    selected: list[DocumentText] = []
    for name in payload.names:
        if name not in allowed:
            raise ValueError(
                f"unknown or unsafe document name: {name!r}; use a known document"
            )
        path = _DOCUMENT_DIR / name
        selected.append(
            DocumentText(
                name=name, title=_title_for(path), text=path.read_text(encoding="utf-8")
            )
        )
    return ReadDocumentsOutput(documents=selected)


def _title_for(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return path.stem.replace("-", " ").title()


registry = [list_documents, read_documents]
