import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initialState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftAuthoringClient,
  type DraftAuthoringClient,
} from "../domain/draft-authoring-client.js";
import type { CapabilityDetail } from "../domain/capability-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { CreateDraftDialog } from "./CreateDraftDialog.js";
import type { DraftWorkspaceController } from "../routes/useDraftWorkspace.js";
import { useDraftWorkspace } from "../routes/useDraftWorkspace.js";

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/draft-authoring-client.js", () => ({
  createDraftAuthoringClient: vi.fn(),
}));

vi.mock("../routes/useDraftWorkspace.js", () => ({
  useDraftWorkspace: vi.fn(),
}));

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateDraftAuthoringClient = vi.mocked(createDraftAuthoringClient);
const mockedUseDraftWorkspace = vi.mocked(useDraftWorkspace);

const capability: CapabilityDetail = {
  kind: "node_spec",
  name: "local.documents.read",
  sourceId: "local.documents",
  description: "Read documents.",
  isAsync: false,
  outcomes: ["ok", "error"],
  inputSchema: { type: "object" },
  outputSchema: { type: "object" },
  wrapperHints: {},
  acceptsContext: true,
};

const workspace = (workspaceId: string): DraftWorkspace => ({
  workspaceId,
  revision: 1,
  title: "Existing draft",
  status: "invalid",
  diagnostics: [],
  summary: { name: "existing", start: null, stepCount: 0, routeCount: 0, steps: [] },
  draft: null,
});

const controller: DraftWorkspaceController = {
  listPhase: "ready",
  detailPhase: "idle",
  items: [workspace("draft-existing")],
  selected: null,
  listMessage: null,
  detailMessage: null,
  refresh: vi.fn(),
};

const authoringClient: DraftAuthoringClient = {
  createEmpty: vi.fn(),
  createFromCapability: vi.fn(),
  addCapabilityStep: vi.fn(),
  updateCapabilityStep: vi.fn(),
  setRoute: vi.fn(),
  validate: vi.fn(),
};

const DraftDestination = () => {
  const location = useLocation();
  return <p>Destination: {location.pathname}{location.search}</p>;
};

const renderDialog = (selectedCapability: CapabilityDetail | null = capability) =>
  render(
    <MemoryRouter initialEntries={["/console/discover"]}>
      <Routes>
        <Route
          path="/console/discover"
          element={<CreateDraftDialog capability={selectedCapability} onClose={vi.fn()} />}
        />
        <Route path="/console/drafts/:workspaceId" element={<DraftDestination />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: initialState(),
    connectedTarget: "http://workflow.test/rpc",
    recordEvidence: vi.fn(),
    readExecutor: null,
    writeExecutor: { run: vi.fn() },
  });
  mockedCreateDraftAuthoringClient.mockReturnValue(authoringClient);
  mockedUseDraftWorkspace.mockReturnValue(controller);
});

afterEach(() => cleanup());

describe("CreateDraftDialog", () => {
  it("uses a native modal lifecycle with focus and cancel handling", async () => {
    const user = userEvent.setup();
    const DialogHarness = () => {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)} type="button">
            Open dialog
          </button>
          {open && <CreateDraftDialog capability={null} onClose={() => setOpen(false)} />}
        </>
      );
    };

    render(
      <MemoryRouter initialEntries={["/console/discover"]}>
        <DialogHarness />
      </MemoryRouter>,
    );
    const opener = screen.getByRole("button", { name: "Open dialog" });
    await user.click(opener);

    const dialog = screen.getByRole("dialog");
    expect(dialog.tagName).toBe("DIALOG");
    expect(dialog).toHaveAttribute("open");
    expect(screen.getByRole("textbox", { name: "Workspace id" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(opener).toHaveFocus();

    await user.click(opener);
    const reopenedDialog = screen.getByRole("dialog");
    fireEvent(reopenedDialog, new Event("cancel", { bubbles: true, cancelable: true }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(opener).toHaveFocus();
  });

  it("offers an existing draft and a seeded capability draft", async () => {
    const user = userEvent.setup();
    renderDialog();

    expect(screen.getByRole("dialog", { name: "Add capability to draft" })).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Existing draft" }), "draft-existing");
    await user.click(screen.getByRole("button", { name: "Use existing draft" }));

    expect(await screen.findByText("Destination: /console/drafts/draft-existing?capability=local.documents.read")).toBeInTheDocument();
  });

  it("uses the canonical workspace id returned by seeded creation", async () => {
    const user = userEvent.setup();
    vi.mocked(authoringClient.createFromCapability).mockResolvedValue(workspace("canonical-created"));
    renderDialog();

    await user.type(screen.getByRole("textbox", { name: "Workspace id" }), "requested-id");
    await user.type(screen.getByRole("textbox", { name: "Draft name" }), "report-workflow");
    await user.click(screen.getByRole("button", { name: "Create seeded draft" }));

    expect(await screen.findByText("Destination: /console/drafts/canonical-created?capability=local.documents.read")).toBeInTheDocument();
  });

  it("creates an empty draft when no capability was handed off", async () => {
    const user = userEvent.setup();
    vi.mocked(authoringClient.createEmpty).mockResolvedValue(workspace("canonical-empty"));
    renderDialog(null);

    await user.type(screen.getByRole("textbox", { name: "Workspace id" }), "requested-id");
    await user.type(screen.getByRole("textbox", { name: "Draft name" }), "report-workflow");
    await user.click(screen.getByRole("button", { name: "Create draft" }));

    expect(authoringClient.createEmpty).toHaveBeenCalledWith({
      workspaceId: "requested-id",
      name: "report-workflow",
      title: "",
    });
    expect(await screen.findByText("Destination: /console/drafts/canonical-empty")).toBeInTheDocument();
  });
});
