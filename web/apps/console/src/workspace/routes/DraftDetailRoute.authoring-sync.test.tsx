import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { DraftDetailRoute } from "./DraftDetailRoute.js";

vi.mock("./useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

vi.mock("../authoring/DraftWorkbench.js", () => ({
  DraftWorkbench: ({
    draft,
    onDraftChange,
  }: {
    readonly draft: DraftWorkspace;
    readonly onDraftChange?: (draft: DraftWorkspace) => void;
  }) => (
    <section aria-label="Mock draft workbench">
      <button
        onClick={() => onDraftChange?.({ ...draft, revision: 4, status: "valid" })}
        type="button"
      >
        Commit current draft
      </button>
      <Link to="/console/drafts/other">Open other workspace</Link>
    </section>
  ),
}));

const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);

let loadedReport: DraftWorkspace;
let loadedOther: DraftWorkspace;

const workspace = (overrides: Partial<DraftWorkspace> = {}): DraftWorkspace => ({
  workspaceId: "draft-report",
  revision: 1,
  title: "Report",
  status: "invalid",
  diagnostics: [],
  summary: { name: "report", start: "collect", stepCount: 1, routeCount: 0, steps: ["collect"] },
  draft: { nodes: [{ id: "collect" }] },
  ...overrides,
});

const controller = (selected: DraftWorkspace | null): DraftWorkspaceController => ({
  listPhase: "ready",
  detailPhase: selected === null ? "loading" : "ready",
  items: [],
  selected,
  listMessage: null,
  detailMessage: null,
  refresh: vi.fn(),
});

const renderRoute = () => render(
  <MemoryRouter initialEntries={["/console/drafts/draft-report"]}>
    <Routes>
      <Route path="/console/drafts/:workspaceId" element={<DraftDetailRoute />} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  loadedReport = workspace();
  loadedOther = workspace({ workspaceId: "other", title: "Other", revision: 9, status: "valid" });
  mockedUseDraftWorkspace.mockImplementation((workspaceId) => controller(
    workspaceId === "draft-report"
      ? loadedReport
      : loadedOther,
  ));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DraftDetailRoute authoring freshness", () => {
  it("reflects committed workbench state, accepts loader refreshes, and clears it across workspaces", async () => {
    const user = userEvent.setup();
    const route = renderRoute();

    expect(screen.getByText("Revision 1")).toBeInTheDocument();
    expect(screen.getByText("Invalid")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Commit current draft" }));
    expect(screen.getByText("Revision 4")).toBeInTheDocument();
    expect(screen.getByText("Valid")).toBeInTheDocument();

    loadedReport = workspace({ revision: 7, status: "invalid" });
    route.rerender(
      <MemoryRouter initialEntries={["/console/drafts/draft-report"]}>
        <Routes>
          <Route path="/console/drafts/:workspaceId" element={<DraftDetailRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Revision 7")).toBeInTheDocument());
    expect(screen.getByText("Invalid")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Open other workspace" }));
    expect(screen.getByRole("heading", { name: "Other" })).toBeInTheDocument();
    expect(screen.getByText("Revision 9")).toBeInTheDocument();
    expect(screen.getByText("Valid")).toBeInTheDocument();
    expect(screen.queryByText("Revision 4")).toBeNull();
  });
});
