import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthoringContractInventory } from "../domain/authoring-contract-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";
import { WorkflowContractInspector } from "./WorkflowContractInspector.js";

afterEach(cleanup);

const draft: DraftWorkspace = {
  workspaceId: "draft-report",
  revision: 4,
  title: "Report",
  status: "invalid",
  diagnostics: [],
  summary: { name: "report", start: "read", stepCount: 2, routeCount: 0, steps: ["read", "render"] },
  draft: {
    input_schema: { type: "object", properties: { query: { type: "string" } } },
    state_schema: { type: "object", properties: { report: { type: "string", reducer: "wf.std.replace" } } },
    output_schema: { type: "object", properties: { report: { type: "string" } } },
    outcomes: ["ok", "cancelled"],
    output: [{ path: "state.report", target: "report" }],
    steps: {},
    routes: {},
  },
};

const option = (path: string, origin: "workflow_input" | "workflow_state" | "runtime_context" | "workflow_output") => ({
  path,
  label: path,
  origin,
  schema: {},
  required: false,
  availability: "available" as const,
  uses: ["workflow_output" as const],
});

const inventory: AuthoringContractInventory = {
  workspaceId: "draft-report",
  revision: 4,
  selectedStepId: null,
  readableSources: [option("input.query", "workflow_input"), option("state.report", "workflow_state"), option("context.request_id", "runtime_context")],
  stepInputTargets: [],
  stepOutputSources: [],
  stateTargets: [],
  workflowOutputTargets: [option("output.report", "workflow_output")],
  entrySteps: [
    { stepId: "read", label: "Read" },
    { stepId: "render", label: "Render" },
  ],
  workflowOutcomes: ["ok", "cancelled"],
  warnings: [],
};

const controller = {
  draft,
  selection: { kind: "contract", contract: "input" },
  insertionContext: null,
  dirty: false,
  phase: "idle",
  message: null,
  resetGeneration: 0,
  preservedCapabilityForm: null,
  addCapability: vi.fn(), updateCapability: vi.fn(), setStepInputs: vi.fn(), setStepOutputs: vi.fn(),
  setContract: vi.fn(), setStart: vi.fn(), setWorkflowOutputBindings: vi.fn(),
  updateSetup: vi.fn(), setRoute: vi.fn(), validate: vi.fn(), reload: vi.fn(), reapply: vi.fn(),
  rememberCapabilityForm: vi.fn(), rememberRouteForm: vi.fn(), select: vi.fn(), markDirty: vi.fn(),
} satisfies DraftAuthoringController;

describe("WorkflowContractInspector", () => {
  it("edits the input schema and entry step from inventory", async () => {
    const user = userEvent.setup();
    render(<WorkflowContractInspector contract="input" controller={controller} draft={draft} inventory={inventory} />);

    expect(screen.getByRole("textbox", { name: "Field name" })).toHaveValue("query");
    await user.selectOptions(screen.getByRole("combobox", { name: "Entry step" }), "render");
    await user.click(screen.getByRole("button", { name: "Save entry step" }));
    expect(controller.setStart).toHaveBeenCalledWith("render");
  });

  it("offers output sources without presenting runtime context as a normal choice", () => {
    render(<WorkflowContractInspector contract="output" controller={controller} draft={draft} inventory={inventory} />);

    expect(screen.getByRole("button", { name: /state\.report/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /context\.request_id/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save output bindings" })).toBeInTheDocument();
  });

  it("submits ordered, unique, non-blank outcomes", async () => {
    const user = userEvent.setup();
    render(<WorkflowContractInspector contract="outcomes" controller={controller} draft={draft} inventory={inventory} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Outcome 2" }), { target: { value: "ok" } });
    await user.click(screen.getByRole("button", { name: "Save outcomes" }));
    expect(controller.setContract).toHaveBeenCalledWith({ outcomes: ["ok"] });
  });
});
