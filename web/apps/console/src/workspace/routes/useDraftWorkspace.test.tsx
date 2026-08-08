import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ConnectionState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import type { DraftWorkspaceClient } from "../domain/draft-workspace-client.js";
import type {
  DraftWorkspace,
  DraftWorkspacePage,
} from "../domain/draft-workspace-models.js";
import { createDraftWorkspaceClient } from "../domain/draft-workspace-client.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/draft-workspace-client.js", async () => {
  const actual = await vi.importActual<typeof import("../domain/draft-workspace-client.js")>(
    "../domain/draft-workspace-client.js",
  );
  return { ...actual, createDraftWorkspaceClient: vi.fn() };
});

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateDraftWorkspaceClient = vi.mocked(createDraftWorkspaceClient);

const connectedState = {
  phase: "connected",
  connectedTarget: "http://workflow.example/rpc",
} as ConnectionState;

const disconnectedState = {
  phase: "not_configured",
  connectedTarget: null,
} as ConnectionState;

const workspace = (
  workspaceId: string,
  overrides: Partial<DraftWorkspace> = {},
): DraftWorkspace => ({
  workspaceId,
  revision: 1,
  title: `${workspaceId} title`,
  status: "valid",
  diagnostics: [],
  summary: {
    name: workspaceId,
    start: "start",
    stepCount: 1,
    routeCount: 1,
    steps: ["start"],
  },
  draft: { nodes: [] },
  ...overrides,
});

const page = (items: ReadonlyArray<DraftWorkspace>): DraftWorkspacePage => ({
  items: [...items],
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const client = {
  list: vi.fn<DraftWorkspaceClient["list"]>(),
  load: vi.fn<DraftWorkspaceClient["load"]>(),
} satisfies DraftWorkspaceClient;

const readExecutor = {} as ConsoleReadExecutor;

beforeEach(() => {
  client.list.mockReset();
  client.load.mockReset();
  mockedCreateDraftWorkspaceClient.mockReset();
  mockedCreateDraftWorkspaceClient.mockReturnValue(client);
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: connectedState,
    connectedTarget: connectedState.connectedTarget,
    recordEvidence: vi.fn(),
    readExecutor,
    writeExecutor: null,
  });
});

afterEach(() => cleanup());

describe("useDraftWorkspace", () => {
  it("loads the list and URL-owned detail through the draft client", async () => {
    client.list.mockResolvedValue(page([workspace("draft-report")]));
    client.load.mockResolvedValue(workspace("draft-report"));

    const { result } = renderHook(() => useDraftWorkspace("draft-report"));

    await waitFor(() => expect(result.current.listPhase).toBe("ready"));
    await waitFor(() => expect(result.current.detailPhase).toBe("ready"));

    expect(client.list).toHaveBeenCalledOnce();
    expect(client.load).toHaveBeenCalledWith("draft-report");
    expect(result.current.items[0]?.workspaceId).toBe("draft-report");
    expect(result.current.selected?.workspaceId).toBe("draft-report");
  });

  it("ignores a late detail response after the URL workspace changes", async () => {
    client.list.mockResolvedValue(page([]));
    const firstDetail = deferred<DraftWorkspace>();
    const secondDetail = deferred<DraftWorkspace>();
    client.load
      .mockReturnValueOnce(firstDetail.promise)
      .mockReturnValueOnce(secondDetail.promise);

    const { result, rerender } = renderHook(
      ({ workspaceId }: { workspaceId: string | null }) => useDraftWorkspace(workspaceId),
      { initialProps: { workspaceId: "draft-first" } },
    );

    await waitFor(() => expect(client.load).toHaveBeenCalledWith("draft-first"));
    rerender({ workspaceId: "draft-second" });
    await waitFor(() => expect(client.load).toHaveBeenCalledWith("draft-second"));

    firstDetail.resolve(workspace("draft-first"));
    secondDetail.resolve(workspace("draft-second"));

    await waitFor(() => expect(result.current.selected?.workspaceId).toBe("draft-second"));
    expect(result.current.selected?.workspaceId).not.toBe("draft-first");
  });

  it("does not expose a loaded detail during URL or target transitions", async () => {
    client.list.mockResolvedValue(page([workspace("draft-first")]));
    client.load
      .mockResolvedValueOnce(workspace("draft-first"))
      .mockReturnValueOnce(deferred<DraftWorkspace>().promise)
      .mockReturnValueOnce(deferred<DraftWorkspace>().promise);

    const renders: Array<{ items: ReadonlyArray<DraftWorkspace>; selected: DraftWorkspace | null }> = [];
    const { result, rerender } = renderHook(
      ({ workspaceId }: { workspaceId: string | null }) => {
        const current = useDraftWorkspace(workspaceId);
        renders.push({ items: current.items, selected: current.selected });
        return current;
      },
      { initialProps: { workspaceId: "draft-first" } },
    );
    await waitFor(() => expect(result.current.selected?.workspaceId).toBe("draft-first"));

    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://new-workflow.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: {} as ConsoleReadExecutor,
      writeExecutor: null,
    });
    const renderCountBeforeTargetChange = renders.length;
    rerender({ workspaceId: "draft-first" });
    expect(renders[renderCountBeforeTargetChange]?.items).toEqual([]);
    expect(renders[renderCountBeforeTargetChange]?.selected).toBeNull();

    rerender({ workspaceId: "draft-second" });
    expect(result.current.selected).toBeNull();
  });

  it("preserves the loaded list while refresh reloads the relevant reads", async () => {
    client.list
      .mockResolvedValueOnce(page([workspace("draft-old")]))
      .mockReturnValueOnce(deferred<DraftWorkspacePage>().promise);
    client.load
      .mockResolvedValueOnce(workspace("draft-old"))
      .mockReturnValueOnce(deferred<DraftWorkspace>().promise);

    const { result } = renderHook(() => useDraftWorkspace("draft-old"));
    await waitFor(() => expect(result.current.selected?.workspaceId).toBe("draft-old"));

    act(() => {
      result.current.refresh();
      result.current.refresh();
    });

    expect(result.current.items[0]?.workspaceId).toBe("draft-old");
    expect(client.list).toHaveBeenCalledTimes(2);
    expect(client.load).toHaveBeenCalledTimes(2);
  });

  it("coalesces a simultaneous target and URL change into one detail read", async () => {
    client.list
      .mockResolvedValueOnce(page([workspace("draft-old")]))
      .mockResolvedValueOnce(page([workspace("draft-new")]));
    client.load
      .mockResolvedValueOnce(workspace("draft-old"))
      .mockResolvedValueOnce(workspace("draft-new"));

    const { result, rerender } = renderHook(
      ({ workspaceId }: { workspaceId: string | null }) => useDraftWorkspace(workspaceId),
      { initialProps: { workspaceId: "draft-old" } },
    );
    await waitFor(() => expect(result.current.selected?.workspaceId).toBe("draft-old"));

    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://new-workflow.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: {} as ConsoleReadExecutor,
      writeExecutor: null,
    });
    rerender({ workspaceId: "draft-new" });

    await waitFor(() => expect(result.current.selected?.workspaceId).toBe("draft-new"));
    expect(client.list).toHaveBeenCalledTimes(2);
    expect(client.load).toHaveBeenCalledTimes(2);
  });

  it("clears stale data and reloads both reads after reconnect", async () => {
    client.list
      .mockResolvedValueOnce(page([workspace("draft-old")]))
      .mockResolvedValueOnce(page([workspace("draft-new")]))
      .mockResolvedValueOnce(page([workspace("draft-new")]));
    client.load
      .mockResolvedValueOnce(workspace("draft-old"))
      .mockResolvedValueOnce(workspace("draft-new"));

    const { result, rerender } = renderHook(() => useDraftWorkspace("draft-new"));
    await waitFor(() => expect(result.current.listPhase).toBe("ready"));
    await waitFor(() => expect(result.current.detailPhase).toBe("ready"));

    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://new-workflow.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: {} as ConsoleReadExecutor,
      writeExecutor: null,
    });
    rerender();

    expect(result.current.items).toEqual([]);
    expect(result.current.selected).toBeNull();
    await waitFor(() => expect(result.current.items[0]?.workspaceId).toBe("draft-new"));
    expect(client.list).toHaveBeenCalledTimes(2);
    expect(client.load).toHaveBeenCalledTimes(2);
  });

  it("reports list and detail errors without claiming ready data", async () => {
    client.list.mockRejectedValue(new Error("list failed"));
    client.load.mockRejectedValue(new Error("detail failed"));

    const { result } = renderHook(() => useDraftWorkspace("draft-broken"));

    await waitFor(() => expect(result.current.listPhase).toBe("error"));
    await waitFor(() => expect(result.current.detailPhase).toBe("error"));

    expect(result.current.items).toEqual([]);
    expect(result.current.selected).toBeNull();
    expect(result.current.listMessage).toBe("list failed");
    expect(result.current.detailMessage).toBe("detail failed");
  });

  it("does not request drafts while disconnected", () => {
    mockedUseConsoleWorkspace.mockReturnValue({
      connection: disconnectedState,
      connectedTarget: null,
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: null,
    });

    const { result } = renderHook(() => useDraftWorkspace("draft-report"));

    expect(result.current.listPhase).toBe("disconnected");
    expect(result.current.detailPhase).toBe("disconnected");
    expect(client.list).not.toHaveBeenCalled();
    expect(client.load).not.toHaveBeenCalled();
  });
});
