import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import { DraftDetailRoute } from "./DraftDetailRoute.js";
import { formatBoundedJson } from "../authoring/format-bounded-json.js";

const globalStyles = readFileSync(
  "src/styles/global.css",
  "utf8",
);

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

  it("uses a capability query only as the workbench's initial browser selection", () => {
    renderRoute("draft-report?capability=local.documents.read%2Fv2");

    expect(screen.getByRole("heading", { name: "local.documents.read/v2" })).toBeInTheDocument();
    expect(screen.getByText("Draft authoring workbench")).toBeInTheDocument();
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

  it("keeps the raw draft closed and marks deferred mutation controls unavailable", () => {
    const { container } = renderRoute();

    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Undo — Later" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByRole("button", { name: "Delete node — Later" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.queryByRole("link", { name: /compile|artifact|save|edit|mutate/i })).toBeNull();
  });

  it("makes the raw JSON region focusable and names its horizontal scrolling behavior", () => {
    renderRoute();

    const rawJson = screen.getByRole("region", {
      name: "Raw draft JSON, horizontally scrollable",
    });
    expect(rawJson).toHaveAttribute("tabindex", "0");
  });

  it("does not render a selected workspace whose identity differs from the URL", () => {
    mockedUseDraftWorkspace.mockReturnValue(
      controller({ selected: workspace({ workspaceId: "draft-old" }) }),
    );
    renderRoute("draft-new");

    expect(screen.queryByRole("heading", { name: "Quarterly report" })).toBeNull();
    expect(screen.getByText("draft-new")).toBeInTheDocument();
  });

  it("keeps detail panels stackable at the mobile workspace breakpoint", () => {
    renderRoute();

    expect(document.querySelector(".draft-detail__panels")).toBeInTheDocument();
    expect(globalStyles).toMatch(
      /@media \(max-width: 850px\)[\s\S]*?\.draft-detail__panels\s*\{[\s\S]*?grid-template-columns:\s*1fr/,
    );
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
