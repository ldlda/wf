import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";
import { ContextInspector } from "./ContextInspector.js";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const draft: DraftWorkspace = {
  workspaceId: "draft-report",
  revision: 3,
  title: "Report",
  status: "invalid",
  diagnostics: [],
  summary: {
    name: "report",
    start: "read",
    stepCount: 1,
    routeCount: 0,
    steps: ["read"],
  },
  draft: {
    steps: {
      read: {
        use: "demo.read",
        input: [
          { target: "title", value: "Existing title" },
          { target: "count", path: "input.count" },
        ],
        desc: "Read the report",
        retry: 2,
        timeout_seconds: 45,
      },
    },
    routes: {},
  },
};

const detail: CapabilityDetail = {
  kind: "node_spec",
  name: "demo.read",
  sourceId: "demo",
  description: "Read a report",
  isAsync: false,
  outcomes: ["ok"],
  inputSchema: {
    type: "object",
    properties: {
      title: { type: "string" },
      count: { type: "integer" },
    },
  },
  outputSchema: { type: "object", properties: {} },
  wrapperHints: {},
  acceptsContext: false,
};

const controller = {
  draft,
  selection: { kind: "node", nodeId: "read" },
  insertionContext: null,
  dirty: false,
  phase: "idle",
  message: null,
  resetGeneration: 0,
  addCapability: vi.fn(),
  updateCapability: vi.fn(),
  setStepInputs: vi.fn(),
  setStepOutputs: vi.fn(),
  updateSetup: vi.fn(),
  setRoute: vi.fn(),
  validate: vi.fn(),
  reload: vi.fn(),
  reapply: vi.fn(),
  select: vi.fn(),
  markDirty: vi.fn(),
  rememberCapabilityForm: vi.fn(),
  rememberRouteForm: vi.fn(),
  preservedCapabilityForm: null,
} satisfies DraftAuthoringController;

describe("ContextInspector", () => {
  it("binds the inspected capability schema and canonical node values", () => {
    render(
      <ContextInspector
        capabilities={[]}
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={draft}
        selection={{ kind: "node", nodeId: "read" }}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue("Read the report");
    expect(screen.getByRole("textbox", { name: "Step id" })).toHaveAttribute("readonly");
    expect(screen.getByRole("spinbutton", { name: "Retry" })).toHaveValue(2);
    expect(screen.getByRole("spinbutton", { name: "Timeout seconds" })).toHaveValue(45);
    fireEvent.click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveValue("title");
    expect(screen.getByRole("combobox", { name: "Source path for input row 2" })).toHaveValue("input.count");
  });

  it("keeps deferred actions focusable while keyboard activation does not dispatch", async () => {
    const user = userEvent.setup();
    render(
      <ContextInspector
        capabilities={[]}
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={draft}
        selection={{ kind: "node", nodeId: "read" }}
      />,
    );

    const deferred = screen.getAllByRole("button", { name: /Later/ });
    expect(screen.getByText("These actions are not available in this workbench yet.")).toBeInTheDocument();
    expect(deferred).toHaveLength(6);
    deferred[0]?.focus();
    for (const [index, action] of deferred.entries()) {
      if (index > 0) await user.tab();
      expect(document.activeElement).toBe(action);
      expect(action).toHaveAttribute("aria-disabled", "true");
      expect(action).not.toBeDisabled();
      await user.keyboard("{Enter}");
      await user.keyboard(" ");
    }

    expect(controller.addCapability).not.toHaveBeenCalled();
    expect(controller.updateCapability).not.toHaveBeenCalled();
    expect(controller.setRoute).not.toHaveBeenCalled();
    expect(controller.validate).not.toHaveBeenCalled();
  });

  it("maps server diagnostics to the selected node form", () => {
    const diagnosticDraft: DraftWorkspace = {
      ...draft,
      diagnostics: [
        {
          code: "invalid_input",
          path: "steps[read].input.title",
          message: "Title is not accepted.",
          stepId: "read",
          repairHint: null,
          details: {},
        },
        {
          code: "invalid_retry",
          path: "steps[read].retry",
          message: "Retry must be non-negative.",
          stepId: "read",
          repairHint: null,
          details: {},
        },
        {
          code: "invalid_node_input_field",
          path: "bindings[0].target",
          message: "Destination field is not declared.",
          stepId: "read",
          repairHint: null,
          details: {},
        },
      ],
    };

    render(
      <ContextInspector
        capabilities={[]}
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={diagnosticDraft}
        selection={{ kind: "node", nodeId: "read" }}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getAllByText("Title is not accepted.")).not.toHaveLength(0);
    expect(screen.getAllByText("Retry must be non-negative.")).not.toHaveLength(0);
    expect(screen.getAllByText("Destination field is not declared.")).not.toHaveLength(0);
    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("keeps the editable update form when a conflict has no canonical draft", () => {
    const conflictDraft: DraftWorkspace = {
      ...draft,
      status: "conflict",
      diagnostics: [],
      summary: { ...draft.summary, steps: [] },
      draft: null,
    };
    const preservedController = {
      ...controller,
      draft: conflictDraft,
      preservedCapabilityForm: {
        kind: "update" as const,
        input: {
          stepId: "read",
          capabilityName: "demo.read",
          description: "Locally edited description",
          retry: 3,
          timeoutSeconds: 60,
          inputBindings: [{ target: "title", value: "Locally edited title" }],
        },
      },
    } satisfies DraftAuthoringController;

    render(
      <ContextInspector
        capabilities={[]}
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={preservedController}
        draft={conflictDraft}
        selection={{ kind: "node", nodeId: "read" }}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      "Locally edited description",
    );
    fireEvent.click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue(
      "Locally edited title",
    );
  });
});
