import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";
import { ContextInspector } from "./ContextInspector.js";

afterEach(() => cleanup());

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
    expect(screen.getByRole("spinbutton", { name: "Retry" })).toHaveValue(2);
    expect(screen.getByRole("spinbutton", { name: "Timeout seconds" })).toHaveValue(45);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Existing title");
    expect(screen.getByRole("textbox", { name: "Source path for Count" })).toHaveValue("input.count");
    expect(screen.getAllByText("Bind")).not.toHaveLength(0);
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
          path: "nodes[0].input[0].target",
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

    expect(screen.getAllByText("Title is not accepted.")).not.toHaveLength(0);
    expect(screen.getAllByText("Retry must be non-negative.")).not.toHaveLength(0);
    expect(screen.getAllByText("Destination field is not declared.")).not.toHaveLength(0);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveAttribute(
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
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue(
      "Locally edited title",
    );
  });
});
