from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_api.models import HealthResult, JsonProjector


def test_json_projector_validates_transport_neutral_payloads() -> None:
    project_health = JsonProjector(HealthResult)

    assert project_health({"status": "ok", "store_root": "store"}) == {
        "status": "ok",
        "store_root": "store",
    }


def test_json_projector_rejects_malformed_payloads() -> None:
    project_health = JsonProjector(HealthResult)

    with pytest.raises(ValidationError):
        project_health({"status": "ok"})
