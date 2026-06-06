import json
import sys

from examples.demo_workflow import build_demo_registry, build_demo_workflow
from wf_core import RunState, execute_workflow, resume_workflow


def print_run(label: str, run: RunState) -> None:
    print(f"{label}:")
    print(json.dumps(run.to_dict(), indent=2))


def main() -> None:
    workflow = build_demo_workflow()
    registry = build_demo_registry()

    report = workflow.validate_structure()
    report.raise_for_errors()
    print("Workflow is structurally valid.", file=sys.stderr)

    interrupted_run = execute_workflow(
        workflow,
        {"folder_id": "demo-folder", "should_email": True},
        registry,
    )
    print_run("Interrupting run", interrupted_run)

    resumed_run = resume_workflow(
        workflow,
        interrupted_run,
        registry,
        resume_payload={"approved": True, "comment": "Looks good to send."},
        resume_outcome="submitted",
    )
    print_run("Resumed run", resumed_run)

    non_interrupt_run = execute_workflow(
        workflow,
        {"folder_id": "demo-folder", "should_email": False},
        registry,
    )
    print_run("Non-interrupt run", non_interrupt_run)


if __name__ == "__main__":
    main()
