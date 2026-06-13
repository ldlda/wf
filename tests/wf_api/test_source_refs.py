from __future__ import annotations

import pytest

from wf_api.source_refs import SourceResourceRef


def test_source_resource_ref_requires_logical_source_and_uri() -> None:
    ref = SourceResourceRef(
        logical_source="drive",
        uri="gdrive://file/abc",
        mime_type="application/pdf",
        name="Report.pdf",
    )

    assert ref.kind == "source_resource_ref"
    assert ref.logical_source == "drive"
    assert ref.uri == "gdrive://file/abc"
    assert ref.model_dump(mode="json")["name"] == "Report.pdf"


def test_source_resource_ref_rejects_empty_logical_source() -> None:
    with pytest.raises(ValueError):
        SourceResourceRef(logical_source="", uri="gdrive://file/abc")
