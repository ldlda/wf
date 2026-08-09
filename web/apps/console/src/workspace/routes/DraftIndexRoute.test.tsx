import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { initialState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftAuthoringClient,
  type DraftAuthoringClient,
} from "../domain/draft-authoring-client.js";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import { DraftIndexRoute } from "./DraftIndexRoute.js";

vi.mock("./useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/draft-authoring-client.js", () => ({
  createDraftAuthoringClient: vi.fn(),
}));

const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);
const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateDraftAuthoringClient = vi.mocked(createDraftAuthoringClient);

const workspace = (
  workspaceId: string,
  overrides: Partial<DraftWorkspace> = {},
): DraftWorkspace => ({
  workspaceId,
  revision: 4,
  title: "Quarterly report",
  status: "invalid",
  diagnostics: [],
  summary: {
    name: "report-workflow",
    start: "collect",
    stepCount: 3,
    routeCount: 4,
    steps: ["collect", "summarize", "publish"],
  },
  draft: null,
  ...overrides,
});

const controller = (
  overrides: Partial<DraftWorkspaceController> = {},
): DraftWorkspaceController => ({
  listPhase: "ready",
  detailPhase: "idle",
  items: [workspace("draft-report")],
  selected: null,
  listMessage: null,
  detailMessage: null,
  refresh: vi.fn(),
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
  mockedUseDraftWorkspace.mockReturnValue(controller());
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

const DraftDestination = () => {
  const location = useLocation();
  return <p>Draft destination: {location.pathname}{location.search}</p>;
};

describe("DraftIndexRoute", () => {
  it("shows the draft heading and a row link owned by each workspace id", () => {
    mockedUseDraftWorkspace.mockReturnValue(
      controller({
        items: [
          workspace("draft-report"),
          workspace("draft-no-title", { title: null }),
        ],
      }),
    );

    render(
      <MemoryRouter>
        <DraftIndexRoute />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Draft workspaces" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quarterly report" })).toHaveAttribute(
      "href",
      "/console/drafts/draft-report",
    );
    expect(screen.getByRole("link", { name: "draft-no-title" })).toHaveAttribute(
      "href",
      "/console/drafts/draft-no-title",
    );
  });

  it("renders revision, status, step count, and route count in each row", () => {
    render(
      <MemoryRouter>
        <DraftIndexRoute />
      </MemoryRouter>,
    );

    const row = screen.getByRole("row", { name: /Quarterly report/i });
    expect(row).toHaveTextContent("Revision 4");
    expect(row).toHaveTextContent("Invalid");
    expect(row).toHaveTextContent("3 steps");
    expect(row).toHaveTextContent("4 routes");
  });

  it.each([
    ["empty", "No draft workspaces are available.", { items: [], listPhase: "ready" as const }],
    ["error", "DraftWorkspacePage is malformed", { items: [], listPhase: "error" as const, listMessage: "DraftWorkspacePage is malformed" }],
  ] as const)("renders an explicit %s state", (_name, message, overrides) => {
    mockedUseDraftWorkspace.mockReturnValue(controller(overrides));
    render(
      <MemoryRouter>
        <DraftIndexRoute />
      </MemoryRouter>,
    );

    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("creates a draft from the index and routes by the canonical workspace id", async () => {
    const user = userEvent.setup();
    const created = workspace("canonical-draft-id", { title: "Created draft" });
    vi.mocked(authoringClient.createEmpty).mockResolvedValue(created);
    render(
      <MemoryRouter initialEntries={["/console/drafts"]}>
        <Routes>
          <Route path="/console/drafts" element={<DraftIndexRoute />} />
          <Route path="/console/drafts/:workspaceId" element={<DraftDestination />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "New draft" }));
    await user.type(screen.getByRole("textbox", { name: "Workspace id" }), "requested-draft");
    await user.type(screen.getByRole("textbox", { name: "Draft name" }), "report-workflow");
    await user.type(screen.getByRole("textbox", { name: "Title" }), "Created draft");
    await user.click(screen.getByRole("button", { name: "Create draft" }));

    expect(authoringClient.createEmpty).toHaveBeenCalledWith({
      workspaceId: "requested-draft",
      name: "report-workflow",
      title: "Created draft",
    });
    expect(await screen.findByText("Draft destination: /console/drafts/canonical-draft-id")).toBeInTheDocument();
  });
});
