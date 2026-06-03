from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import Field

from wf_api.source_registry import (
    AtomicJsonRegistryStore,
    SourceRegistryBaseModel,
    validate_source_registry_id,
    validate_unique_source_ids,
)


class FakeEntry(SourceRegistryBaseModel):
    id: str


class FakeRegistry(SourceRegistryBaseModel):
    version: int = 1
    entries: list[FakeEntry] = Field(default_factory=list)


def test_validate_source_registry_id_accepts_normal_ids() -> None:
    assert validate_source_registry_id("github.work") == "github.work"
    assert validate_source_registry_id("my_source") == "my_source"
    assert validate_source_registry_id("test-v1") == "test-v1"


def test_validate_source_registry_id_rejects_unsafe_ids() -> None:
    with pytest.raises(ValueError, match="source id must start"):
        validate_source_registry_id("../bad")
    with pytest.raises(ValueError, match="source id must start"):
        validate_source_registry_id("has space")
    with pytest.raises(ValueError, match="source id must start"):
        validate_source_registry_id("")


def test_validate_unique_source_ids_accepts_unique_ids() -> None:
    entries = [FakeEntry(id="a"), FakeEntry(id="b")]
    validate_unique_source_ids(entries)


def test_validate_unique_source_ids_rejects_duplicate_ids() -> None:
    entries = [FakeEntry(id="a"), FakeEntry(id="a")]
    with pytest.raises(ValueError, match="duplicate source id 'a'"):
        validate_unique_source_ids(entries)


def test_validate_unique_source_ids_rejects_non_string_id() -> None:
    entries: list[object] = [FakeEntry(id="a"), object()]
    with pytest.raises(
        ValueError, match="source registry entries must expose string id"
    ):
        validate_unique_source_ids(entries)


def test_atomic_json_registry_store_loads_empty_when_missing(tmp_path: Path) -> None:
    store = AtomicJsonRegistryStore(
        tmp_path,
        filename="registry.json",
        registry_type=FakeRegistry,
        empty_factory=FakeRegistry,
        corrupt_label="test registry",
    )

    registry = store.load_registry()

    assert registry.version == 1
    assert registry.entries == []
    assert store.path == tmp_path / "registry.json"


def test_atomic_json_registry_store_round_trips(tmp_path: Path) -> None:
    store = AtomicJsonRegistryStore(
        tmp_path,
        filename="registry.json",
        registry_type=FakeRegistry,
        empty_factory=FakeRegistry,
        corrupt_label="test registry",
    )
    registry = FakeRegistry(entries=[FakeEntry(id="test.entry")])

    store.save_registry(registry)
    loaded = store.load_registry()

    assert len(loaded.entries) == 1
    assert loaded.entries[0].id == "test.entry"


def test_atomic_json_registry_store_rejects_corrupted_json(tmp_path: Path) -> None:
    store = AtomicJsonRegistryStore(
        tmp_path,
        filename="registry.json",
        registry_type=FakeRegistry,
        empty_factory=FakeRegistry,
        corrupt_label="test registry",
    )
    store.path.write_text("not json{{{", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupted"):
        store.load_registry()


def test_source_registry_base_model_rejects_extra_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        SourceRegistryBaseModel.model_validate({"unknown_field": "value"})
