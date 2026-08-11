import { cleanup, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import type { CapabilityDiscoveryController } from "./useCapabilityDiscovery.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";
import { DiscoverRoute } from "./DiscoverRoute.js";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftAuthoringClient,
  type DraftAuthoringClient,
} from "../domain/draft-authoring-client.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { initialState } from "../../app/state.js";

vi.mock("./useCapabilityDiscovery.js", () => ({
  useCapabilityDiscovery: vi.fn(),
}));

vi.mock("./useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/draft-authoring-client.js", () => ({
  createDraftAuthoringClient: vi.fn(),
}));

const mockedUseCapabilityDiscovery = vi.mocked(useCapabilityDiscovery);
const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);
const globalStyles = readFileSync("src/styles/global.css", "utf8");
const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateDraftAuthoringClient = vi.mocked(createDraftAuthoringClient);

const summary = {
  kind: "node_spec" as const,
  name: "local.documents.read",
  sourceId: "local.documents",
  description: "Read project documents.",
  outcomes: ["ok", "error"],
  inputFields: ["names"],
  outputFields: ["documents"],
};

const draft = (workspaceId: string): DraftWorkspace => ({
  workspaceId,
  revision: 1,
  title: "Existing draft",
  status: "invalid",
  diagnostics: [],
  summary: {
    name: "existing",
    start: null,
    stepCount: 0,
    routeCount: 0,
    steps: [],
  },
  draft: null,
});

const draftController = (): DraftWorkspaceController => ({
  listPhase: "ready",
  detailPhase: "idle",
  items: [draft("draft-existing")],
  selected: null,
  listMessage: null,
  detailMessage: null,
  refresh: vi.fn(),
});

const controller = (
  overrides: Partial<CapabilityDiscoveryController> = {},
): CapabilityDiscoveryController => ({
  phase: "ready",
  query: "",
  sourceId: "",
  items: [summary],
  selected: null,
  nextCursor: null,
  message: null,
  setQuery: vi.fn(),
  setSourceId: vi.fn(),
  search: vi.fn(),
  loadMore: vi.fn(),
  inspect: vi.fn(),
  ...overrides,
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

beforeEach(() => {
  mockedUseCapabilityDiscovery.mockReturnValue(controller());
  mockedUseDraftWorkspace.mockReturnValue(draftController());
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: initialState(),
    connectedTarget: "http://workflow.test/rpc",
    recordEvidence: vi.fn(),
    readExecutor: null,
    writeExecutor: { run: vi.fn() },
  });
  mockedCreateDraftAuthoringClient.mockReturnValue(authoringClient);
});
afterEach(() => cleanup());

const renderRoute = () =>
  render(
    <MemoryRouter initialEntries={["/console/discover"]}>
      <Routes>
        <Route path="/console/discover" element={<DiscoverRoute />} />
        <Route path="/console/drafts/:workspaceId" element={<DraftDestination />} />
      </Routes>
    </MemoryRouter>,
  );

const DraftDestination = () => {
  const location = useLocation();
  return <p>Draft destination: {location.pathname}{location.search}</p>;
};

describe("DiscoverRoute", () => {
  it("shows the discovery heading and searchable source-filtered controls", () => {
    renderRoute();

    expect(screen.getByRole("heading", { name: "Discover capabilities" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Search capabilities" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Filter by source" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("renders compact capability rows with contract summary fields", async () => {
    const inspect = vi.fn();
    mockedUseCapabilityDiscovery.mockReturnValue(controller({ inspect }));
    renderRoute();

    expect(screen.getByText("Node spec")).toBeInTheDocument();
    expect(screen.getByText("Source: local.documents")).toBeInTheDocument();
    expect(screen.getByText("Inputs: names")).toBeInTheDocument();
    expect(screen.getByText("Outputs: documents")).toBeInTheDocument();
    expect(screen.getByText("Outcomes: ok, error")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /local\.documents\.read/i }));
    expect(inspect).toHaveBeenCalledWith("local.documents.read");
  });

  it.each([
    ["disconnected", "Connect a workflow server to discover capabilities."],
    ["loading", "Loading capabilities..."],
    ["error", "CapabilityPage is malformed"],
  ] as const)("renders an explicit %s state", (phase, message) => {
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({ phase, message: phase === "error" ? message : null, items: [] }),
    );
    renderRoute();

    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("renders selected input/output schemas and wrapper hints", () => {
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({
        selected: {
          ...summary,
          isAsync: false,
          inputSchema: { type: "object", properties: { names: { type: "array" } } },
          outputSchema: { type: "object", properties: { documents: { type: "array" } } },
          wrapperHints: { input: "names", output: "documents" },
          acceptsContext: true,
        },
      }),
    );
    renderRoute();

    expect(screen.getByRole("tab", { name: "Contract" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Try capability" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Input schema" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Output schema" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Wrapper hints" })).toBeInTheDocument();
    const contractPanel = screen.getByRole("tabpanel", { name: "Contract" });
    expect(within(contractPanel).getAllByText(/"names"/)).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Add to draft" })).toBeInTheDocument();
  });

  it("keeps a disconnected operation state inline with the selected capability", async () => {
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({
        selected: {
          ...summary,
          isAsync: false,
          inputSchema: { type: "object", properties: {} },
          outputSchema: {},
          wrapperHints: {},
          acceptsContext: false,
        },
      }),
    );
    mockedUseConsoleWorkspace.mockReturnValue({
      connection: initialState(),
      connectedTarget: null,
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: null,
    });
    renderRoute();

    await userEvent.click(screen.getByRole("tab", { name: "Try capability" }));

    expect(
      screen.getByText("Capability calls are unavailable until a workflow server is connected."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Capabilities" })).toBeInTheDocument();
  });

  it("exposes selected row state and associates the result with its detail", () => {
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({
        selected: {
          ...summary,
          isAsync: false,
          inputSchema: {},
          outputSchema: {},
          wrapperHints: {},
          acceptsContext: true,
        },
      }),
    );
    renderRoute();

    const row = screen.getByRole("button", { name: /local\.documents\.read/i });
    expect(row).toHaveAttribute("aria-pressed", "true");
    expect(row).toHaveAttribute("aria-controls", "capability-detail");
    expect(screen.getByRole("region", { name: "local.documents.read" })).toHaveAttribute(
      "id",
      "capability-detail",
    );
  });

  it("shows load more only when the controller has a next cursor", async () => {
    const loadMore = vi.fn();
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({ nextCursor: "page-2", loadMore }),
    );
    renderRoute();

    await userEvent.click(screen.getByRole("button", { name: "Load more capabilities" }));
    expect(loadMore).toHaveBeenCalledOnce();

    cleanup();
    mockedUseCapabilityDiscovery.mockReturnValue(controller());
    renderRoute();
    expect(screen.queryByRole("button", { name: "Load more capabilities" })).toBeNull();
  });

  it("disables load more while the controller is loading", () => {
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({ phase: "loading", nextCursor: "page-2" }),
    );
    render(<DiscoverRoute />);

    expect(screen.getByRole("button", { name: "Load more capabilities" })).toBeDisabled();
  });

  it("hands an inspected capability to an existing draft through the URL", async () => {
    const user = userEvent.setup();
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({
        selected: {
          ...summary,
          isAsync: false,
          inputSchema: {},
          outputSchema: {},
          wrapperHints: {},
          acceptsContext: true,
        },
      }),
    );
    renderRoute();

    await user.click(screen.getByRole("button", { name: "Add to draft" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Existing draft" }), "draft-existing");
    await user.click(screen.getByRole("button", { name: "Use existing draft" }));

    expect(
      await screen.findByText("Draft destination: /console/drafts/draft-existing?capability=local.documents.read"),
    ).toBeInTheDocument();
  });

  it("creates a seeded draft and routes by the canonical workspace id", async () => {
    const user = userEvent.setup();
    const created = draft("canonical-created-id");
    vi.mocked(authoringClient.createFromCapability).mockResolvedValue(created);
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({
        selected: {
          ...summary,
          isAsync: false,
          inputSchema: {},
          outputSchema: {},
          wrapperHints: {},
          acceptsContext: true,
        },
      }),
    );
    renderRoute();

    await user.click(screen.getByRole("button", { name: "Add to draft" }));
    await user.type(screen.getByRole("textbox", { name: "Workspace id" }), "requested-id");
    await user.type(screen.getByRole("textbox", { name: "Draft name" }), "seeded-report");
    await user.click(screen.getByRole("button", { name: "Create seeded draft" }));

    expect(authoringClient.createFromCapability).toHaveBeenCalledWith({
      workspaceId: "requested-id",
      name: "seeded-report",
      title: "",
      capabilityName: "local.documents.read",
    });
    expect(
      await screen.findByText(
        "Draft destination: /console/drafts/canonical-created-id?capability=local.documents.read",
      ),
    ).toBeInTheDocument();
  });

  it("keeps both discovery panes scrollable within the viewport", () => {
    expect(globalStyles).toMatch(
      /\.capability-discovery__results,\s*\.capability-discovery__detail,\s*\.capability-playground\s*\{[\s\S]*?max-height:\s*calc\(100vh - 10rem\);[\s\S]*?overflow-y:\s*auto/,
    );
  });
});
