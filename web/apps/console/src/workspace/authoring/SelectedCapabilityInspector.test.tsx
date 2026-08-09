import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { SelectedCapabilityInspector } from "./SelectedCapabilityInspector.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";

afterEach(() => cleanup());

const detail: CapabilityDetail = {
  kind: "node_spec",
  name: "demo.read",
  sourceId: "demo",
  description: "Read a report",
  isAsync: false,
  outcomes: ["ok"],
  inputSchema: { type: "object", properties: { title: { type: "string" } } },
  outputSchema: { type: "object", properties: { text: { type: "string" } } },
  wrapperHints: {},
  acceptsContext: false,
};

const draft = (stepId: string, input: unknown, output: unknown): DraftWorkspace => ({
  workspaceId: "draft-report",
  revision: 3,
  title: "Report",
  status: "invalid",
  diagnostics: [],
  summary: { name: "report", start: stepId, stepCount: 1, routeCount: 0, steps: [stepId] },
  draft: {
    state_schema: { type: "object", properties: { existing: { type: "string" } } },
    steps: {
      [stepId]: {
        use: "demo.read",
        input,
        output,
        desc: "Read the report",
        retry: 2,
        timeout_seconds: 45,
      },
    },
    routes: {},
  },
});

const controllerFor = (workspace: DraftWorkspace): DraftAuthoringController => ({
  draft: workspace,
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
  rememberCapabilityForm: vi.fn(),
  rememberRouteForm: vi.fn(),
  select: vi.fn(),
  markDirty: vi.fn(),
  preservedCapabilityForm: null,
});

describe("SelectedCapabilityInspector", () => {
  it("composes setup, inputs, and outputs while preserving malformed rows and dispatching focused saves", async () => {
    const user = userEvent.setup();
    const workspace = draft(
      "read",
      [
        { target: "title", value: "Existing title" },
        { target: "broken", value: () => "not JSON" },
      ],
      [
        { source: "text", target: "state.existing" },
        { source: "text", target: "not-state" },
      ],
    );
    const controller = controllerFor(workspace);

    render(
      <SelectedCapabilityInspector
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={workspace}
        nodeKind="use"
        nodeRef="demo.read"
        stepId="read"
      />,
    );

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(3);
    expect(screen.getByRole("tab", { name: "Setup" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getByRole("region", { name: "Raw unsupported input row 2" })).toHaveTextContent("broken");
    await user.click(screen.getByRole("button", { name: "Save inputs" }));
    expect(controller.setStepInputs).not.toHaveBeenCalled();
    expect(screen.getAllByRole("alert").some((alert) =>
      alert.textContent?.includes("Remove or repair every unsupported input row before saving.") ?? false,
    )).toBe(true);

    await user.click(screen.getByRole("button", { name: "Remove unsupported input row 2" }));
    await user.click(screen.getByRole("button", { name: "Save inputs" }));
    expect(controller.setStepInputs).toHaveBeenCalledWith([{ target: "title", value: "Existing title" }]);

    await user.click(screen.getByRole("tab", { name: "Outputs" }));
    expect(screen.getByRole("region", { name: "Raw unsupported output row 2" })).toHaveTextContent(
      "not-state",
    );
    await user.click(screen.getByRole("button", { name: "Save outputs" }));
    expect(controller.setStepOutputs).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Clear outputs" }));
    expect(controller.setStepOutputs).not.toHaveBeenCalled();
    expect(screen.getAllByRole("alert").some((alert) =>
      alert.textContent?.includes("Remove or repair this unsupported output row before clearing outputs.") ?? false,
    )).toBe(true);
    await user.click(screen.getByRole("button", { name: "Remove unsupported output row 2" }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));
    expect(controller.setStepOutputs).toHaveBeenCalledWith([
      { source: "text", target: "state.existing" },
    ]);

    await user.click(screen.getByRole("tab", { name: "Setup" }));
    await user.click(screen.getByRole("button", { name: "Save setup" }));
    expect(controller.updateSetup).toHaveBeenCalledWith({});
  });

  it("keeps explicit null and singleton binding containers visible as unsupported rows", async () => {
    const user = userEvent.setup();
    const workspace = draft(
      "read",
      null,
      { source: "text", target: "state.existing" },
    );
    const controller = controllerFor(workspace);

    render(
      <SelectedCapabilityInspector
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={workspace}
        nodeKind="use"
        nodeRef="demo.read"
        stepId="read"
      />,
    );

    await user.click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getByRole("region", { name: "Raw unsupported input row 1" })).toHaveTextContent("null");
    await user.click(screen.getByRole("button", { name: "Save inputs" }));
    expect(controller.setStepInputs).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "Outputs" }));
    expect(screen.getByRole("region", { name: "Raw unsupported output row 1" })).toHaveTextContent("text");
    await user.click(screen.getByRole("button", { name: "Save outputs" }));
    expect(controller.setStepOutputs).not.toHaveBeenCalled();
  });

  it("keeps diagnostic ids unique across failing setup and hidden binding forms", async () => {
    const user = userEvent.setup();
    const workspace = draft(
      "read",
      [{ target: "title", value: "Existing title" }],
      [{ source: "text", target: "state.existing" }],
    );
    const controller = controllerFor(workspace);

    render(
      <SelectedCapabilityInspector
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={workspace}
        nodeKind="use"
        nodeRef="demo.read"
        stepId="read"
      />,
    );

    fireEvent.change(screen.getByRole("spinbutton", { name: "Retry", hidden: true }), {
      target: { value: "-1" },
    });
    await user.click(screen.getByRole("button", { name: "Save setup" }));
    await user.click(screen.getByRole("tab", { name: "Inputs" }));
    await user.clear(screen.getByRole("combobox", { name: "Target for row 1" }));
    await user.click(screen.getByRole("button", { name: "Save inputs" }));
    await user.click(screen.getByRole("tab", { name: "Outputs" }));
    await user.clear(screen.getByRole("combobox", { name: "Target for output row 1" }));
    await user.click(screen.getByRole("button", { name: "Save outputs" }));

    const diagnosticIds = [...document.querySelectorAll('[id$="-error"], [id$="-errors"]')]
      .map((element) => element.id);
    expect(new Set(diagnosticIds).size).toBe(diagnosticIds.length);
    expect(diagnosticIds.length).toBeGreaterThanOrEqual(3);
  });

  it("rehydrates canonical rows when the selected step changes", async () => {
    const first = draft("first", [{ target: "title", value: "First" }], []);
    const second = draft("second", [{ target: "title", value: "Second" }], []);
    const controller = controllerFor(first);
    const { rerender } = render(
      <SelectedCapabilityInspector
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={controller}
        draft={first}
        nodeKind="use"
        nodeRef="demo.read"
        stepId="first"
      />,
    );

    await userEvent.setup().click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveValue("title");
    rerender(
      <SelectedCapabilityInspector
        capabilityDetail={detail}
        capabilityDetailMessage={null}
        capabilityDetailPhase="ready"
        controller={{ ...controller, draft: second }}
        draft={second}
        key="second"
        nodeKind="use"
        nodeRef="demo.read"
        stepId="second"
      />,
    );
    await userEvent.setup().click(screen.getByRole("tab", { name: "Inputs" }));
    expect(screen.getByRole("combobox", { name: "Target for row 1" })).toHaveValue("title");
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Second");
  });

  it.each([
    ["loading", "Loading capability schema..."],
    ["error", "Capability schema failed to load."],
  ] as const)("shows capability detail %s feedback", (phase, message) => {
    const workspace = draft("read", [], []);
    render(
      <SelectedCapabilityInspector
        capabilityDetail={phase === "loading" ? null : detail}
        capabilityDetailMessage={phase === "error" ? null : message}
        capabilityDetailPhase={phase}
        controller={controllerFor(workspace)}
        draft={workspace}
        nodeKind="use"
        nodeRef="demo.read"
        stepId="read"
      />,
    );
    expect(screen.getByRole(phase === "error" ? "alert" : "status")).toHaveTextContent(message);
  });
});
