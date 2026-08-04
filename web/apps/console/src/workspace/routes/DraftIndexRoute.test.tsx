import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { DraftWorkspaceController } from "./useDraftWorkspace.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import { DraftIndexRoute } from "./DraftIndexRoute.js";

vi.mock("./useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);

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

beforeEach(() => mockedUseDraftWorkspace.mockReturnValue(controller()));
afterEach(() => cleanup());

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
});
