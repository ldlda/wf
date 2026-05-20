from __future__ import annotations

from collections.abc import Callable
from typing import cast

from wf_core import END, RuntimeContext, Workflow

DemoHandler = Callable[[dict[str, object], RuntimeContext], dict[str, object]]


def build_demo_workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "name": "drive_summary_demo",
            "input_schema": {
                "type": "object",
                "properties": {
                    "folder_id": {"type": "string"},
                    "should_email": {"type": "boolean"},
                },
                "required": ["folder_id", "should_email"],
            },
            "state_schema": {
                "fields": {
                    "folder_id": {"type": "string"},
                    "should_email": {"type": "boolean"},
                    "documents": {"type": "array", "reducer": "wf.std.replace"},
                    "item_summaries": {"type": "array", "reducer": "wf.std.append"},
                    "summary": {"type": "string", "reducer": "wf.std.replace"},
                    "approved": {"type": "boolean", "reducer": "wf.std.replace"},
                    "approval_comment": {
                        "type": "string",
                        "reducer": "wf.std.replace",
                    },
                    "email_status": {"type": "string", "reducer": "wf.std.replace"},
                }
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "email_status": {"type": "string"},
                },
                "required": ["summary", "email_status"],
            },
            "node_defs": [
                {
                    "name": "drive_list_files",
                    "input_schema": {
                        "type": "object",
                        "properties": {"folder_id": {"type": "string"}},
                        "required": ["folder_id"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"documents": {"type": "array"}},
                        "required": ["documents"],
                    },
                    "outcomes": ["ok"],
                },
                {
                    "name": "summarize_document",
                    "input_schema": {
                        "type": "object",
                        "properties": {"document": {"type": "string"}},
                        "required": ["document"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"item_summary": {"type": "string"}},
                        "required": ["item_summary"],
                    },
                    "outcomes": ["ok"],
                },
                {
                    "name": "combine_summaries",
                    "input_schema": {
                        "type": "object",
                        "properties": {"item_summaries": {"type": "array"}},
                        "required": ["item_summaries"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                    },
                    "outcomes": ["ok"],
                },
                {
                    "name": "send_email",
                    "input_schema": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"email_status": {"type": "string"}},
                        "required": ["email_status"],
                    },
                    "outcomes": ["sent"],
                },
                {
                    "name": "mark_email_skipped",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"email_status": {"type": "string"}},
                        "required": ["email_status"],
                    },
                    "outcomes": ["ok"],
                },
            ],
            "start": "list_files",
            "nodes": [
                {
                    "id": "list_files",
                    "type": "node",
                    "node": "drive_list_files",
                    "desc": "List files from a Google Drive folder",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["folder_id"]},
                            "path": {"root": "input", "parts": ["folder_id"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["documents"]},
                            "target": {"root": "state", "parts": ["documents"]},
                        }
                    ],
                },
                {
                    "id": "summarize_each",
                    "type": "foreach",
                    "over": "state.documents",
                    "as": "document",
                    "mode": "serial",
                    "on_item_error": "fail",
                },
                {
                    "id": "summarize_one",
                    "type": "node",
                    "node": "summarize_document",
                    "desc": "Summarize one document",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["document"]},
                            "path": {"root": "context", "parts": ["document"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["item_summary"]},
                            "target": {"root": "state", "parts": ["item_summaries"]},
                        }
                    ],
                },
                {
                    "id": "combine_summaries",
                    "type": "node",
                    "node": "combine_summaries",
                    "desc": "Combine item summaries into one final summary",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["item_summaries"]},
                            "path": {"root": "state", "parts": ["item_summaries"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["summary"]},
                            "target": {"root": "state", "parts": ["summary"]},
                        }
                    ],
                },
                {
                    "id": "should_email",
                    "type": "condition",
                    "check": {
                        "op": "eq",
                        "left": {"path": "state.should_email"},
                        "right": {"value": True},
                    },
                },
                {
                    "id": "send_email",
                    "type": "node",
                    "node": "send_email",
                    "desc": "Send the summary by email",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["summary"]},
                            "path": {"root": "state", "parts": ["summary"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["email_status"]},
                            "target": {"root": "state", "parts": ["email_status"]},
                        }
                    ],
                },
                {
                    "id": "approve_email",
                    "type": "interrupt",
                    "kind": "approval",
                    "request_map": {
                        "state.summary": "summary",
                        "input.folder_id": "folder_id",
                    },
                    "out_map": {
                        "approved": "state.approved",
                        "comment": "state.approval_comment",
                    },
                    "outcomes": ["submitted", "cancelled"],
                },
                {
                    "id": "skip_email",
                    "type": "node",
                    "node": "mark_email_skipped",
                    "desc": "Record that email delivery was skipped",
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["email_status"]},
                            "target": {"root": "state", "parts": ["email_status"]},
                        }
                    ],
                },
            ],
            "edges": [
                {"from": "list_files", "outcome": "ok", "to": "summarize_each"},
                {"from": "summarize_each", "outcome": "loop", "to": "summarize_one"},
                {
                    "from": "summarize_each",
                    "outcome": "done",
                    "to": "combine_summaries",
                },
                {"from": "summarize_one", "outcome": "ok", "to": END},
                {"from": "combine_summaries", "outcome": "ok", "to": "should_email"},
                {"from": "should_email", "outcome": "true", "to": "approve_email"},
                {"from": "should_email", "outcome": "false", "to": "skip_email"},
                {"from": "approve_email", "outcome": "submitted", "to": "send_email"},
                {"from": "approve_email", "outcome": "cancelled", "to": "skip_email"},
                {"from": "send_email", "outcome": "sent", "to": END},
                {"from": "skip_email", "outcome": "ok", "to": END},
            ],
        }
    )


def drive_list_files(
    payload: dict[str, object], ctx: RuntimeContext
) -> dict[str, object]:
    folder_id = payload["folder_id"]
    return {
        "outcome": "ok",
        "output": {
            "documents": [
                f"{folder_id}/meeting-notes.md",
                f"{folder_id}/weekly-report.md",
            ]
        },
    }


def summarize_documents(
    payload: dict[str, object], ctx: RuntimeContext
) -> dict[str, object]:
    document = payload["document"]
    return {
        "outcome": "ok",
        "output": {"item_summary": f"Summary of {document}"},
    }


def combine_summaries(
    payload: dict[str, object], ctx: RuntimeContext
) -> dict[str, object]:
    raw_item_summaries = cast(list[object], payload["item_summaries"])
    item_summaries = [str(item) for item in raw_item_summaries]
    return {
        "outcome": "ok",
        "output": {"summary": " | ".join(item_summaries)},
    }


def send_email(payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
    return {
        "outcome": "sent",
        "output": {"email_status": f"sent: {payload['summary']}"},
    }


def mark_email_skipped(
    payload: dict[str, object], ctx: RuntimeContext
) -> dict[str, object]:
    return {
        "outcome": "ok",
        "output": {"email_status": "skipped"},
    }


def build_demo_registry() -> dict[str, DemoHandler]:
    return {
        "drive_list_files": drive_list_files,
        "summarize_document": summarize_documents,
        "combine_summaries": combine_summaries,
        "send_email": send_email,
        "mark_email_skipped": mark_email_skipped,
    }
