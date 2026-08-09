import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { DraftWorkbench } from "./DraftWorkbench.js";

vi.mock("./useAuthoringCapabilityDetail.js", () => ({
  useAuthoringCapabilityDetail: vi.fn(),
}));

import { useAuthoringCapabilityDetail } from "./useAuthoringCapabilityDetail.js";

const mockedUseAuthoringCapabilityDetail = vi.mocked(useAuthoringCapabilityDetail);

const workspace: DraftWorkspace = {
  workspaceId: "draft-review",
  revision: 2,
  title: "Review workflow",
  status: "invalid",
  diagnostics: [
    {
      code: "missing_route",
      path: "routes.review",
      message: "Review needs a route.",
      stepId: "review",
      repairHint: "Add a submitted route.",
      details: {},
    },
  ],
  summary: {
    name: "review-workflow",
    start: "collect",
    stepCount: 2,
    routeCount: 1,
    steps: ["collect", "review"],
  },
  draft: {
    name: "review-workflow",
    start: "collect",
    steps: { collect: { use: "demo.collect" }, review: { interrupt: { kind: "approval" } } },
    routes: { collect: { ok: "review" } },
  },
};

const capabilityDetail: CapabilityDetail = {
  kind: "node_spec",
  name: "demo.collect",
  sourceId: "demo",
  description: "Collect source material.",
  isAsync: false,
  outcomes: ["ok"],
  inputSchema: { type: "object", properties: {} },
  outputSchema: { type: "object", properties: {} },
  wrapperHints: {},
  acceptsContext: false,
};

const dataflowCapabilityDetail: CapabilityDetail = {
  ...capabilityDetail,
  inputSchema: {
    type: "object",
    properties: { title: { type: "string" } },
  },
  outputSchema: {
    type: "object",
    properties: { text: { type: "string" } },
  },
};

const setViewport = (width: number): void => {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
beforeEach(() => {
  setViewport(1024);
  mockedUseAuthoringCapabilityDetail.mockReturnValue({
    phase: "disconnected",
    detail: null,
    message: null,
  });
});

describe("DraftWorkbench", () => {
  it("keeps palette, graph, and inspector visible in the desktop shell", () => {
    render(
      <DraftWorkbench
        draft={workspace}
        capabilities={[
          {
            kind: "node_spec",
            name: "demo.collect",
            sourceId: "demo",
            description: "Collect source material.",
            outcomes: ["ok"],
            inputFields: [],
            outputFields: [],
          },
        ]}
      />,
    );

    expect(screen.getByRole("region", { name: "Capability palette" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Workflow graph" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Context inspector" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "demo.collect" })).toBeInTheDocument();
    expect(screen.getByText("Draft summary")).toBeInTheDocument();
    expect(screen.getByText("Review needs a route.")).toBeInTheDocument();
  });

  it("keeps the raw draft collapsed and exposes all deferred actions without handlers", () => {
    render(<DraftWorkbench draft={workspace} />);

    const raw = screen.getByText("Raw draft document").closest("details");
    expect(raw).not.toHaveAttribute("open");
    for (const label of [
      "Undo — Later",
      "Redo — Later",
      "Delete node — Later",
      "Delete route — Later",
      "Add other step — Later",
      "Create artifact — Later",
    ]) {
      const action = screen.getByRole("button", { name: label });
      expect(action).toHaveAttribute("aria-disabled", "true");
      expect(action).not.toBeDisabled();
    }
    expect(screen.getByText("These actions are not available in this workbench yet.")).toBeInTheDocument();
  });

  it("uses named mobile sheets, keeps selection persistent, and returns focus on close", async () => {
    setViewport(390);
    const user = userEvent.setup();
    const { container } = render(
      <DraftWorkbench
        capabilities={[
          {
            kind: "node_spec",
            name: "demo.collect",
            sourceId: "demo",
            description: "Collect source material.",
            outcomes: ["ok"],
            inputFields: [],
            outputFields: [],
          },
        ]}
        draft={workspace}
      />,
    );

    const paletteTrigger = screen.getByRole("button", { name: "Open capability palette" });
    const palette = container.querySelector("#draft-workbench-palette");
    expect(palette).not.toBeNull();
    expect(palette).toHaveAttribute("aria-label", "Capability palette sheet");
    expect(screen.getByRole("region", { name: "Workflow graph" })).toBeInTheDocument();

    await user.click(paletteTrigger);
    expect(palette).toHaveAttribute("open", "");
    await user.click(screen.getByRole("button", { name: "demo.collect" }));
    expect(container.querySelector(".draft-workbench")).toHaveAttribute(
      "data-selection-kind",
      "capability",
    );

    const inspectorTrigger = screen.getByRole("button", { name: "Open context inspector" });
    await user.click(screen.getByRole("button", { name: "Close capability palette" }));
    expect(paletteTrigger).toHaveFocus();
    await user.click(inspectorTrigger);
    const inspector = container.querySelector("#draft-workbench-inspector");
    expect(inspector).toHaveAttribute("aria-label", "Context inspector sheet");
    expect(inspector).toHaveAttribute("open", "");
    expect(within(inspector as HTMLElement).getByText("demo.collect")).toBeInTheDocument();
  });

  it("keeps a dirty inspector form mounted and intact across mobile close and reopen", async () => {
    setViewport(390);
    mockedUseAuthoringCapabilityDetail.mockReturnValue({
      phase: "ready",
      detail: capabilityDetail,
      message: null,
    });
    const user = userEvent.setup();
    const { container } = render(
      <DraftWorkbench
        draft={workspace}
        initialSelection={{ kind: "node", nodeId: "collect" }}
      />,
    );

    const inspector = container.querySelector("#draft-workbench-inspector") as HTMLElement;
    const description = within(inspector).getByRole("textbox", {
      name: "Description",
      hidden: true,
    });
    await user.type(description, " locally edited");
    expect(container.querySelector(".draft-workbench")).toHaveAttribute("data-dirty", "true");

    const inspectorTrigger = screen.getByRole("button", { name: "Open context inspector" });
    await user.click(inspectorTrigger);
    await user.click(screen.getByRole("button", { name: "Close context inspector" }));
    expect(inspectorTrigger).toHaveFocus();
    await user.click(inspectorTrigger);

    expect(
      within(inspector).getByRole("textbox", { name: "Description" }),
    ).toHaveValue(" locally edited");
    expect(container.querySelector(".draft-workbench")).toHaveAttribute("data-dirty", "true");
  });

  it("keeps the selected dataflow tab and unsaved rows across mobile close and reopen", async () => {
    setViewport(390);
    mockedUseAuthoringCapabilityDetail.mockReturnValue({
      phase: "ready",
      detail: dataflowCapabilityDetail,
      message: null,
    });
    const user = userEvent.setup();
    const { container } = render(
      <DraftWorkbench
        draft={workspace}
        initialSelection={{ kind: "node", nodeId: "collect" }}
      />,
    );

    const inspector = container.querySelector("#draft-workbench-inspector") as HTMLElement;
    await user.click(
      within(inspector).getByRole("tab", { name: "Inputs", hidden: true }),
    );
    await user.click(
      within(inspector).getByRole("button", { name: "Add input row", hidden: true }),
    );
    await user.type(
      within(inspector).getByRole("textbox", { name: "Target for row 1", hidden: true }),
      "title",
    );
    await user.click(
      within(inspector).getByRole("tab", { name: "Outputs", hidden: true }),
    );

    const inspectorTrigger = screen.getByRole("button", { name: "Open context inspector" });
    await user.click(inspectorTrigger);
    await user.click(screen.getByRole("button", { name: "Close context inspector" }));
    expect(inspectorTrigger).toHaveFocus();
    await user.click(inspectorTrigger);

    expect(
      within(inspector).getByRole("tab", { name: "Outputs" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      within(inspector).getByRole("textbox", { name: "Target for row 1", hidden: true }),
    ).toHaveValue("title");
  });

  it("rehydrates all selected-step tabs through the graph selection boundary", async () => {
    setViewport(1024);
    mockedUseAuthoringCapabilityDetail.mockReturnValue({
      phase: "ready",
      detail: dataflowCapabilityDetail,
      message: null,
    });
    const twoNodeWorkspace: DraftWorkspace = {
      ...workspace,
      summary: { ...workspace.summary, start: "first", steps: ["first", "second"] },
      draft: {
        name: "review-workflow",
        start: "first",
        steps: {
          first: {
            use: "demo.collect",
            desc: "First setup",
            retry: 1,
            timeout_seconds: 11,
            input: [{ target: "title", value: "first input" }],
            output: [{ source: "text", target: "state.first" }],
          },
          second: {
            use: "demo.collect",
            desc: "Second setup",
            retry: 2,
            timeout_seconds: 22,
            input: [{ target: "title", value: "second input" }],
            output: [{ source: "text", target: "state.second" }],
          },
        },
        routes: { first: { ok: "second" } },
      },
    };
    const user = userEvent.setup();
    const { container } = render(
      <DraftWorkbench
        draft={twoNodeWorkspace}
        initialSelection={{ kind: "node", nodeId: "first" }}
      />,
    );

    const inspector = screen.getByRole("region", { name: "Context inspector" });
    expect(within(inspector).getByRole("heading", { name: "first" })).toBeInTheDocument();
    expect(within(inspector).getByRole("tab", { name: "Setup" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(within(inspector).getByRole("textbox", { name: "Description" })).toHaveValue(
      "First setup",
    );
    await user.click(within(inspector).getByRole("tab", { name: "Inputs" }));
    expect(within(inspector).getByRole("textbox", { name: "Title" })).toHaveValue(
      "first input",
    );
    await user.click(within(inspector).getByRole("tab", { name: "Outputs" }));
    const firstOutputPanel = within(inspector).getByRole("tabpanel", { name: "Outputs" });
    expect(within(firstOutputPanel).getByDisplayValue("state.first")).toBeInTheDocument();

    const secondNode = container.querySelector('[data-node-id="second"]');
    expect(secondNode).not.toBeNull();
    fireEvent.click(secondNode as HTMLElement);

    expect(within(inspector).getByRole("heading", { name: "second" })).toBeInTheDocument();
    expect(within(inspector).getByRole("tab", { name: "Setup" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(within(inspector).getByRole("textbox", { name: "Description" })).toHaveValue(
      "Second setup",
    );
    await user.click(within(inspector).getByRole("tab", { name: "Inputs" }));
    expect(within(inspector).getByRole("textbox", { name: "Title" })).toHaveValue(
      "second input",
    );
    await user.click(within(inspector).getByRole("tab", { name: "Outputs" }));
    const secondOutputPanel = within(inspector).getByRole("tabpanel", { name: "Outputs" });
    expect(within(secondOutputPanel).getByDisplayValue("state.second")).toBeInTheDocument();
  });

  it("reopens an open desktop sheet as a modal after resizing to mobile", async () => {
    setViewport(1024);
    const user = userEvent.setup();
    const { container } = render(<DraftWorkbench draft={workspace} />);
    const inspector = container.querySelector("#draft-workbench-inspector") as HTMLDialogElement;
    const showModal = vi.fn(() => inspector.setAttribute("open", ""));
    Object.defineProperty(inspector, "showModal", { configurable: true, value: showModal });
    Object.defineProperty(inspector, "close", {
      configurable: true,
      value: vi.fn(() => inspector.removeAttribute("open")),
    });

    await user.click(screen.getByRole("button", { name: "Open context inspector" }));
    setViewport(390);
    await act(async () => window.dispatchEvent(new Event("resize")));

    expect(showModal).toHaveBeenCalledTimes(1);
    expect(inspector).toHaveAttribute("open", "");
  });
});
