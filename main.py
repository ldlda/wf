import json
import sys

from wf_core import (
    END,
    RuntimeContext,
    Workflow,
    execute_workflow,
    resume_workflow,
)


workflow = Workflow.model_validate(
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
                "documents": {"type": "array", "merge_strategy": "replace"},
                "summary": {"type": "string", "merge_strategy": "replace"},
                "approved": {"type": "boolean", "merge_strategy": "replace"},
                "approval_comment": {"type": "string", "merge_strategy": "replace"},
                "email_status": {"type": "string", "merge_strategy": "replace"},
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
                "name": "summarize_documents",
                "input_schema": {
                    "type": "object",
                    "properties": {"documents": {"type": "array"}},
                    "required": ["documents"],
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
                "in_map": {"input.folder_id": "folder_id"},
                "out_map": {"documents": "state.documents"},
            },
            {
                "id": "summarize",
                "type": "node",
                "node": "summarize_documents",
                "desc": "Summarize all retrieved documents",
                "in_map": {"state.documents": "documents"},
                "out_map": {"summary": "state.summary"},
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
                "in_map": {"state.summary": "summary"},
                "out_map": {"email_status": "state.email_status"},
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
                "out_map": {"email_status": "state.email_status"},
            },
        ],
        "edges": [
            {"from": "list_files", "outcome": "ok", "to": "summarize"},
            {"from": "summarize", "outcome": "ok", "to": "should_email"},
            {"from": "should_email", "outcome": "true", "to": "approve_email"},
            {"from": "should_email", "outcome": "false", "to": "skip_email"},
            {"from": "approve_email", "outcome": "submitted", "to": "send_email"},
            {"from": "approve_email", "outcome": "cancelled", "to": "skip_email"},
            {"from": "send_email", "outcome": "sent", "to": END},
            {"from": "skip_email", "outcome": "ok", "to": END},
        ],
    }
)

report = workflow.validate_structure()
report.raise_for_errors()

print("Workflow is structurally valid.", file=sys.stderr)


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
    documents = payload["documents"]
    return {
        "outcome": "ok",
        "output": {"summary": f"Summarized {len(documents)} documents from Drive."},
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


registry = {
    "drive_list_files": drive_list_files,
    "summarize_documents": summarize_documents,
    "send_email": send_email,
    "mark_email_skipped": mark_email_skipped,
}

workflow.validate_structure().raise_for_errors()

print("Interrupting run:")
interrupted_run = execute_workflow(
    workflow,
    {"folder_id": "demo-folder", "should_email": True},
    registry,
)
print(json.dumps(interrupted_run.to_dict(), indent=2))

print("Resumed run:")
resumed_run = resume_workflow(
    workflow,
    interrupted_run,
    registry,
    resume_payload={"approved": True, "comment": "Looks good to send."},
    resume_outcome="submitted",
)
print(json.dumps(resumed_run.to_dict(), indent=2))

print("Non-interrupt run:")
non_interrupt_run = execute_workflow(
    workflow,
    {"folder_id": "demo-folder", "should_email": False},
    registry,
)
print(json.dumps(non_interrupt_run.to_dict(), indent=2))
