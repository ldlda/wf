import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { useConsoleWorkspace } from "../context.js";
import type { ConsoleWriteExecutor } from "../domain/write-executor.js";
import type { DraftAuthoringClient } from "../domain/draft-authoring-client.js";
import { createDraftAuthoringClient } from "../domain/draft-authoring-client.js";
import { useAuthoringCapabilityDetail } from "../authoring/useAuthoringCapabilityDetail.js";
import { DraftDetailRoute } from "./DraftDetailRoute.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";
import type { CapabilityDiscoveryController } from "./useCapabilityDiscovery.js";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";

const capture = vi.hoisted(() => ({
  renderCount: 0,
}));

vi.mock("../authoring/DraftWorkbench.js", async () => {
  const actual = await vi.importActual<typeof import("../authoring/DraftWorkbench.js")>(
    "../authoring/DraftWorkbench.js",
  );
  const RealDraftWorkbench = actual.DraftWorkbench;
  return {
    ...actual,
    DraftWorkbench: (props: ComponentProps<typeof RealDraftWorkbench>) => {
      capture.renderCount += 1;
      return <RealDraftWorkbench {...props} />;
    },
  };
});

vi.mock("../context.js", () => ({ useConsoleWorkspace: vi.fn() }));
vi.mock("../domain/draft-authoring-client.js", () => ({
  createDraftAuthoringClient: vi.fn(),
}));
vi.mock("../authoring/useAuthoringCapabilityDetail.js", () => ({
  useAuthoringCapabilityDetail: vi.fn(),
}));
vi.mock("./useCapabilityDiscovery.js", () => ({
  useCapabilityDiscovery: vi.fn(),
}));
vi.mock("./useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateDraftAuthoringClient = vi.mocked(createDraftAuthoringClient);
const mockedUseAuthoringCapabilityDetail = vi.mocked(useAuthoringCapabilityDetail);
const mockedUseCapabilityDiscovery = vi.mocked(useCapabilityDiscovery);
const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);

const detail: CapabilityDetail = {
  kind: "node_spec",
  name: "demo.collect",
  sourceId: "demo",
  description: "Collect source material.",
  isAsync: false,
  outcomes: ["ok"],
  inputSchema: { type: "object", properties: { title: { type: "string" } } },
  outputSchema: { type: "object", properties: { text: { type: "string" } } },
  wrapperHints: {},
  acceptsContext: false,
};

const workspace = (overrides: Partial<DraftWorkspace> = {}): DraftWorkspace => ({
  workspaceId: "draft-report",
  revision: 1,
  title: "Report",
  status: "invalid",
  diagnostics: [],
  summary: { name: "report", start: "collect", stepCount: 1, routeCount: 0, steps: ["collect"] },
  draft: {
    steps: {
      collect: {
        use: "demo.collect",
        desc: "Collect source material.",
        retry: 1,
        timeout_seconds: 30,
      },
    },
    routes: {},
  },
  ...overrides,
});

const otherWorkspace = workspace({
  workspaceId: "other",
  title: "Other",
  revision: 9,
  status: "valid",
});

const controller = (
  selected: DraftWorkspace | null,
  detailPhase: DraftWorkspaceController["detailPhase"],
): DraftWorkspaceController => ({
  listPhase: "ready",
  detailPhase,
  items: [],
  selected,
  listMessage: null,
  detailMessage: null,
  refresh: vi.fn(),
});

const discoveryController = (): CapabilityDiscoveryController => ({
  phase: "ready",
  query: "",
  sourceId: "",
  items: [],
  selected: null,
  nextCursor: null,
  message: null,
  setQuery: vi.fn(),
  setSourceId: vi.fn(),
  search: vi.fn(),
  loadMore: vi.fn(),
  inspect: vi.fn(),
});

const authoringClient: DraftAuthoringClient = {
  createEmpty: vi.fn(),
  createFromCapability: vi.fn(),
  addCapabilityStep: vi.fn(),
  updateCapabilityStep: vi.fn(),
  setStepInputBindings: vi.fn(),
  setStepOutputBindings: vi.fn(),
  setRoute: vi.fn(),
  validate: vi.fn(),
};

const writeExecutor = { run: vi.fn() } as ConsoleWriteExecutor;
let loadedReport: DraftWorkspace;
let loaderPhase: DraftWorkspaceController["detailPhase"];

const NavigateToOtherWorkspace = () => {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate("/console/drafts/other")}>
      Navigate to other workspace
    </button>
  );
};

const routeElement = () => (
  <MemoryRouter initialEntries={["/console/drafts/draft-report"]}>
    <Routes>
      <Route
        path="/console/drafts/:workspaceId"
        element={
          <>
            <DraftDetailRoute />
            <NavigateToOtherWorkspace />
          </>
        }
      />
    </Routes>
  </MemoryRouter>
);

beforeEach(() => {
  vi.clearAllMocks();
  capture.renderCount = 0;
  loadedReport = workspace();
  loaderPhase = "ready";
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: {
      phase: "connected",
      draftTarget: "server-a",
      connectedTarget: "server-a",
      serverStatus: "ok",
      storeRoot: "/tmp",
      durationMs: 1,
      message: null,
      evidence: [],
    },
    connectedTarget: "server-a",
    recordEvidence: vi.fn(),
    readExecutor: writeExecutor,
    writeExecutor,
  });
  mockedCreateDraftAuthoringClient.mockReturnValue(authoringClient);
  mockedUseAuthoringCapabilityDetail.mockReturnValue({
    phase: "ready",
    detail,
    message: null,
  });
  mockedUseCapabilityDiscovery.mockReturnValue(discoveryController());
  mockedUseDraftWorkspace.mockImplementation((workspaceId) => {
    if (loaderPhase !== "ready") return controller(null, loaderPhase);
    return controller(workspaceId === "draft-report" ? loadedReport : otherWorkspace, "ready");
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DraftDetailRoute authoring freshness", () => {
  it("uses real controller mutations and loader replacement without synchronization loops", async () => {
    const user = userEvent.setup();
    const committed = workspace({ revision: 2, status: "valid" });
    vi.mocked(authoringClient.updateCapabilityStep).mockResolvedValueOnce(committed);
    const view = render(routeElement());
    const header = (): HTMLElement => document.querySelector(".draft-detail__header") as HTMLElement;

    const node = document.querySelector('[data-node-id="collect"]');
    expect(node).not.toBeNull();
    fireEvent.click(node as HTMLElement);
    await waitFor(() => expect(screen.getByRole("heading", { name: "collect" })).toBeInTheDocument());
    const retry = screen.getByRole("spinbutton", { name: "Retry" });
    await user.clear(retry);
    await user.type(retry, "2");
    await user.click(screen.getByRole("button", { name: "Save setup" }));
    await waitFor(() => expect(within(header()).getByText("Revision 2")).toBeInTheDocument());
    expect(screen.getByText("Valid")).toBeInTheDocument();
    expect(authoringClient.updateCapabilityStep).toHaveBeenCalledWith(
      expect.objectContaining({ workspaceId: "draft-report", revision: 1, stepId: "collect" }),
    );
    const mutationRenderCount = capture.renderCount;
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
    expect(capture.renderCount).toBe(mutationRenderCount);

    loaderPhase = "loading";
    view.rerender(routeElement());
    expect(screen.getByText("Loading draft workspace...")).toBeInTheDocument();
    loaderPhase = "ready";
    loadedReport = workspace({ revision: 3, status: "invalid" });
    view.rerender(routeElement());
    await waitFor(() => expect(within(header()).getByText("Revision 3")).toBeInTheDocument());
    expect(within(header()).getByText("Invalid")).toBeInTheDocument();
    const refreshRenderCount = capture.renderCount;
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
    expect(capture.renderCount).toBe(refreshRenderCount);

    loaderPhase = "disconnected";
    view.rerender(routeElement());
    expect(screen.getByText("Connect a workflow server to view this draft.")).toBeInTheDocument();
    loaderPhase = "ready";
    view.rerender(routeElement());
    await waitFor(() => expect(within(header()).getByText("Revision 3")).toBeInTheDocument());
    const reconnectRenderCount = capture.renderCount;
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
    expect(capture.renderCount).toBe(reconnectRenderCount);

    await user.click(screen.getByRole("button", { name: "Navigate to other workspace" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Other" })).toBeInTheDocument());
    expect(within(header()).getByText("Revision 9")).toBeInTheDocument();
    const navigationRenderCount = capture.renderCount;
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
    expect(capture.renderCount).toBe(navigationRenderCount);
  });
});
