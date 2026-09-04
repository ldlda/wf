from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

type JsonSchema = Mapping[str, Any]
type ReferenceIdentity = int


class _Resolver(Protocol):
    def lookup(self, ref: str) -> Any: ...

    def in_subresource(self, subresource: Resource[Any]) -> Any: ...


@dataclass(frozen=True, slots=True)
class _Cursor:
    contents: JsonSchema
    resolver: _Resolver
    resource_root: JsonSchema

    def child(self, contents: object) -> _Cursor | None:
        if not isinstance(contents, Mapping):
            return None
        resource = DRAFT202012.create_resource(contents)
        resolver = self.resolver.in_subresource(resource)
        resource_root = contents if resource.id() is not None else self.resource_root
        return _Cursor(contents, resolver, resource_root)

    def referenced(self) -> _Cursor | None:
        reference = self.contents.get("$ref")
        if not isinstance(reference, str):
            return None
        try:
            resolved = self.resolver.lookup(reference)
        except Unresolvable:
            return None
        if not isinstance(resolved.contents, Mapping):
            return None
        return _Cursor(resolved.contents, resolved.resolver, self.resource_root)


@dataclass(frozen=True, slots=True)
class SchemaChild:
    """One declared property plus the reference identities used to reach it."""

    name: str
    view: SchemaView
    active_references: frozenset[ReferenceIdentity]


@dataclass(frozen=True, slots=True)
class SchemaView:
    """A resolver-aware view over one or more candidate JSON Schemas.

    Multiple cursors represent structural alternatives used by workflow path
    discovery. JSON Schema validation itself remains delegated to
    ``jsonschema``; this view answers only the workflow-specific questions
    "which object properties are declared?" and "what schema describes the
    selected foreach item?".
    """

    _cursors: tuple[_Cursor, ...]

    def object_children(
        self,
        *,
        active_references: frozenset[ReferenceIdentity] = frozenset(),
    ) -> tuple[SchemaChild, ...]:
        """Return declared properties, cutting repeated refs on this walk."""
        children: list[SchemaChild] = []
        for cursor in self._cursors:
            for branch, branch_references in _structural_branches(
                cursor, active_references
            ):
                properties = branch.contents.get("properties")
                if not isinstance(properties, Mapping):
                    continue
                for name, child_schema in properties.items():
                    if not isinstance(name, str):
                        continue
                    child = branch.child(child_schema)
                    if child is not None:
                        children.append(
                            SchemaChild(
                                name,
                                SchemaView((child,)),
                                branch_references,
                            )
                        )
        return tuple(children)

    def allows_unknown_properties(self) -> bool:
        """Return whether any structural branch is an open object schema."""
        for cursor in self._cursors:
            for branch, _ in _structural_branches(cursor, frozenset()):
                schema = branch.contents
                if schema == {} or (
                    schema.get("type") == "object"
                    and not isinstance(schema.get("properties"), Mapping)
                    and schema.get("additionalProperties", True) is not False
                ):
                    return True
        return False

    def array_items(self) -> SchemaView | None:
        """Return the first declared homogeneous item schema for an array."""
        for cursor in self._cursors:
            for branch, _ in _structural_branches(cursor, frozenset()):
                schema_type = branch.contents.get("type")
                is_array = schema_type == "array" or (
                    isinstance(schema_type, list) and "array" in schema_type
                )
                if not is_array:
                    continue
                child = branch.child(branch.contents.get("items"))
                if child is not None:
                    return SchemaView((child,))
        return None

    def is_array(self) -> bool:
        """Return whether any structural branch declares an array."""
        return self.array_items() is not None

    def standalone_schema(self) -> dict[str, Any]:
        """Detach this view as a valid Draft 2020-12 schema resource.

        A pure top-level ``$ref`` is replaced by its library-resolved target.
        Sibling keywords remain a true conjunction through ``allOf``. Local
        definition tables travel with the detached schema, and a stable
        absolute ``$id`` makes their fragment references local to this
        embedded resource rather than to a later enclosing context schema.
        """
        cursor = self._cursors[0]
        body: dict[str, Any] = deepcopy(dict(cursor.contents))
        reference = cursor.contents.get("$ref")
        target = cursor.referenced()
        if isinstance(reference, str) and target is not None:
            siblings = {
                key: deepcopy(value)
                for key, value in cursor.contents.items()
                if key != "$ref"
            }
            resolved = deepcopy(dict(target.contents))
            body = {"allOf": [resolved, siblings]} if siblings else resolved
            cursor = target

        definitions = (
            _definition_blocks(cursor.resource_root)
            if _contains_reference(body)
            else {}
        )
        if not definitions:
            return body

        identifier = _resource_identifier(body, definitions)
        if "$id" in body or any(key in body for key in definitions):
            return {"$id": identifier, **definitions, "allOf": [body]}
        return {"$id": identifier, **body, **definitions}


class SchemaNavigator:
    """Resolve JSON Schema references while exposing workflow path semantics."""

    def __init__(self, document: JsonSchema) -> None:
        resource = DRAFT202012.create_resource(document)
        identifier = _resource_identifier(document, {})
        registry = Registry().with_resource(identifier, resource)
        resolver = registry.resolver(identifier).in_subresource(resource)
        self.root = SchemaView((_Cursor(document, resolver, document),))

    def at_path(self, parts: Sequence[str]) -> SchemaView | None:
        """Return the schema view at a declared object-property path."""
        current = self.root
        for part in parts:
            matches = [
                child.view for child in current.object_children() if child.name == part
            ]
            if not matches:
                return None
            current = SchemaView(
                tuple(cursor for match in matches for cursor in match._cursors)
            )
        return current

    def first_unknown(self, parts: Sequence[str]) -> tuple[str | None, str]:
        """Return the first unknown path segment and available keys there."""
        current = self.root
        for part in parts:
            children = current.object_children()
            matches = [child.view for child in children if child.name == part]
            if not matches:
                if current.allows_unknown_properties():
                    return None, ""
                available = ",".join(sorted({child.name for child in children}))
                return part, available
            current = SchemaView(
                tuple(cursor for match in matches for cursor in match._cursors)
            )
        return None, ""


def _structural_branches(
    cursor: _Cursor,
    active_references: frozenset[ReferenceIdentity],
) -> tuple[tuple[_Cursor, frozenset[ReferenceIdentity]], ...]:
    """Expand refs/composition for structural discovery, not validation."""
    branches: list[tuple[_Cursor, frozenset[ReferenceIdentity]]] = [
        (cursor, active_references)
    ]
    target = cursor.referenced()
    if target is not None:
        identity = id(target.contents)
        if identity not in active_references:
            branches.extend(
                _structural_branches(target, active_references | {identity})
            )
    for keyword in ("anyOf", "oneOf", "allOf"):
        members = cursor.contents.get(keyword)
        if not isinstance(members, list):
            continue
        for member in members:
            child = cursor.child(member)
            if child is not None:
                branches.extend(_structural_branches(child, active_references))
    return tuple(branches)


def _definition_blocks(document: JsonSchema) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    for keyword in ("$defs", "definitions"):
        definitions = document.get(keyword)
        if isinstance(definitions, Mapping):
            blocks[keyword] = deepcopy(dict(definitions))
    return blocks


def _contains_reference(schema: object) -> bool:
    """Return whether a detached schema still needs a reference resource."""
    pending = [schema]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            if isinstance(current.get("$ref"), str):
                return True
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _resource_identifier(schema: JsonSchema, definitions: Mapping[str, Any]) -> str:
    payload = json.dumps(
        [schema, definitions],
        sort_keys=True,
        separators=(",", ":"),
        default=repr,
    ).encode()
    return f"urn:wf:schema:{sha256(payload).hexdigest()}"
