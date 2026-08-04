import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import { DraftDetailRoute } from "./DraftDetailRoute.js";

vi.mock("./useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);

const workspace = (overrides: Partial<DraftWorkspace> = {}): DraftWorkspace => ({
  workspaceId: "draft-report",
  revision: 3,
  title: "Quarterly report",
  status: "invalid",
  diagnostics: [
    {
      code: "missing_outcome_edge",
      path: "nodes[summarize].routes",
      message: "The summarize step is missing its ok route.",
      stepId: "summarize",
      repairHint: "Route summarize.ok to __end__.",
      details: {},
    },
  ],
  summary: {
    name: "report-workflow",
    start: "collect",
    stepCount: 2,
    routeCount: 1,
    steps: ["collect", "summarize"],
  },
  draft: {
    nodes: [{ id: "collect" }, { id: "summarize" }],
  },
  ...overrides,
});

const controller = (
  overrides: Partial<DraftWorkspaceController> = {},
): DraftWorkspaceController => ({
  listPhase: "ready",
  detailPhase: "ready",
  items: [],
  selected: workspace(),
  listMessage: null,
  detailMessage: null,
  refresh: vi.fn(),
  ...overrides,
});

const renderRoute = (workspaceId = "draft-report") =>
  render(
    <MemoryRouter initialEntries={[`/console/drafts/${workspaceId}`]}>
      <Routes>
        <Route path="/console/drafts/:workspaceId" element={<DraftDetailRoute />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => mockedUseDraftWorkspace.mockReturnValue(controller()));
afterEach(() => cleanup());

describe("DraftDetailRoute", () => {
  it("uses the URL workspace id and shows prominent status and revision facts", () => {
    renderRoute();

    expect(mockedUseDraftWorkspace).toHaveBeenCalledWith("draft-report");
    const breadcrumbs = screen.getByRole("navigation", { name: "Draft breadcrumbs" });
    expect(breadcrumbs).toHaveTextContent("Drafts");
    expect(breadcrumbs).toHaveTextContent("draft-report");
    expect(screen.getByRole("heading", { name: "Quarterly report" })).toBeInTheDocument();
    expect(screen.getAllByText("Invalid")).not.toHaveLength(0);
    expect(screen.getAllByText("Revision 3")).not.toHaveLength(0);
  });

  it("lists the start step, step ids, and diagnostics beside the summary", () => {
    renderRoute();

    expect(screen.getAllByText("collect")).not.toHaveLength(0);
    expect(screen.getAllByText("summarize")).not.toHaveLength(0);
    expect(screen.getByText("missing_outcome_edge")).toBeInTheDocument();
    expect(screen.getByText("nodes[summarize].routes")).toBeInTheDocument();
    expect(screen.getByText("The summarize step is missing its ok route.")).toBeInTheDocument();
    expect(screen.getByText("Step id")).toBeInTheDocument();
    expect(screen.getByText("Repair hint")).toBeInTheDocument();
    expect(screen.getByText("Route summarize.ok to __end__.")).toBeInTheDocument();
  });

  it("keeps the raw draft closed by default and exposes no mutation controls", () => {
    const { container } = renderRoute();

    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("link", { name: /compile|artifact|save|edit|mutate/i })).toBeNull();
  });

  it("explains when the full draft document was not returned", () => {
    mockedUseDraftWorkspace.mockReturnValue(
      controller({ selected: workspace({ draft: null }) }),
    );
    renderRoute();

    expect(screen.getByText("Full draft document was not returned")).toBeInTheDocument();
  });

  it.each([
    ["disconnected", "Connect a workflow server to view this draft.", { detailPhase: "disconnected" as const, selected: null }],
    ["loading", "Loading draft workspace...", { detailPhase: "loading" as const, selected: null }],
    ["error", "DraftWorkspace is malformed", { detailPhase: "error" as const, selected: null, detailMessage: "DraftWorkspace is malformed" }],
  ] as const)("renders an explicit %s state", (_name, message, overrides) => {
    mockedUseDraftWorkspace.mockReturnValue(controller(overrides));
    renderRoute();

    expect(screen.getByText(message)).toBeInTheDocument();
  });
});
