from __future__ import annotations

from typing import Any


def synthetic_openrpc_document() -> dict[str, Any]:
    return {
        "openrpc": "1.2.6",
        "info": {"title": "ignored", "version": "0"},
        "methods": [
            {
                "name": "workflow.zeta.run",
                "params": [],
                "result": {
                    "name": "workflow.zeta.run_Result",
                    "schema": {"$ref": "#/components/schemas/ZetaResult"},
                },
                "errors": [{"$ref": "#/components/errors/5000"}],
            },
            {
                "name": "workflow.alpha.inspect",
                "params": [
                    {
                        "name": "optional_nullable",
                        "required": False,
                        "schema": {
                            "title": "Optional Nullable",
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "x-future-keyword": {
                                "title": "removed recursively",
                                "value": 1,
                            },
                        },
                    },
                    {
                        "name": "required_closed",
                        "required": True,
                        "schema": {
                            "title": "Required Closed",
                            "type": "object",
                            "additionalProperties": False,
                        },
                    },
                ],
                "result": {
                    "name": "workflow.alpha.inspect_Result",
                    "schema": {"$ref": "#/components/schemas/AlphaResult"},
                },
                "errors": [{"$ref": "#/components/errors/5000"}],
            },
        ],
        "components": {
            "schemas": {
                "ZetaResult": {
                    "title": "Zeta Result",
                    "type": "object",
                    "properties": {"extension": {"additionalProperties": True}},
                },
                "FreeJson": {},
                "AlphaResult": {
                    "title": "Alpha Result",
                    "type": "object",
                    "properties": {
                        "mode": {"title": "Mode", "const": "alpha"},
                        "payload": {},
                        "title": {"title": "Display Title", "type": "string"},
                    },
                    "required": ["mode", "payload", "title"],
                    "$defs": {
                        "title": {
                            "title": "Reusable Title",
                            "type": "string",
                        }
                    },
                    "if": {"properties": {"mode": {"const": "alpha"}}},
                    "then": {"required": ["payload"]},
                    "not": {"required": ["forbidden"]},
                },
            },
            "errors": {
                "5000": {
                    "code": 5000,
                    "message": "Workflow operation failed",
                    "data": {
                        "title": "Error Data",
                        "type": "object",
                        "additionalProperties": False,
                    },
                }
            },
        },
    }
