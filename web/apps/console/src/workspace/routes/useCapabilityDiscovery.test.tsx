import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConnectionState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import type { CapabilityClient } from "../domain/capability-client.js";
import type {
  CapabilityDetail,
  CapabilityPage,
  CapabilitySummary,
} from "../domain/capability-models.js";
import { createCapabilityClient } from "../domain/capability-client.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/capability-client.js", async () => {
  const actual = await vi.importActual<typeof import("../domain/capability-client.js")>(
    "../domain/capability-client.js",
  );
  return { ...actual, createCapabilityClient: vi.fn() };
});

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateCapabilityClient = vi.mocked(createCapabilityClient);

const connectedState = {
  phase: "connected",
  connectedTarget: "http://workflow.example/rpc",
} as ConnectionState;

const disconnectedState = {
  phase: "not_configured",
  connectedTarget: null,
} as ConnectionState;

type NodeSpecSummary = Extract<CapabilitySummary, { readonly kind: "node_spec" }>;

const summary = (name: string, sourceId = "local.documents"): NodeSpecSummary => ({
  kind: "node_spec",
  name,
  sourceId,
  description: `${name} description`,
  outcomes: ["ok", "error"],
  inputFields: ["input"],
  outputFields: ["output"],
});

const detail = (name: string): CapabilityDetail => ({
  ...summary(name),
  isAsync: false,
  inputSchema: { type: "object", properties: { input: { type: "string" } } },
  outputSchema: { type: "object", properties: { output: { type: "string" } } },
  wrapperHints: { note: "Use the selected input field." },
  acceptsContext: true,
});

const page = (
  capabilities: ReadonlyArray<CapabilitySummary>,
  nextCursor: string | null = null,
): CapabilityPage => ({
  capabilities: [...capabilities],
  nextCursor,
  total: capabilities.length,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const client = {
  list: vi.fn<CapabilityClient["list"]>(),
  inspect: vi.fn<CapabilityClient["inspect"]>(),
} satisfies CapabilityClient;

const readExecutor = {} as ConsoleReadExecutor;

beforeEach(() => {
  client.list.mockReset();
  client.inspect.mockReset();
  mockedCreateCapabilityClient.mockReset();
  mockedCreateCapabilityClient.mockReturnValue(client);
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: connectedState,
    connectedTarget: connectedState.connectedTarget,
    recordEvidence: vi.fn(),
    readExecutor,
    writeExecutor: null,
  });
});

describe("useCapabilityDiscovery", () => {
  it("loads the first capability page with the bounded default limit", async () => {
    client.list.mockResolvedValue(page([summary("local.documents.read")]));

    const { result } = renderHook(() => useCapabilityDiscovery());

    await waitFor(() => expect(result.current.phase).toBe("ready"));

    expect(client.list).toHaveBeenCalledWith({ limit: 50 });
    expect(result.current.items[0]?.name).toBe("local.documents.read");
  });

  it("searches with the current query and replaces the list", async () => {
    client.list
      .mockResolvedValueOnce(page([summary("local.documents.read")]))
      .mockResolvedValueOnce(page([summary("local.documents.write")]));
    const { result } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.phase).toBe("ready"));

    act(() => result.current.setQuery("write"));
    act(() => result.current.search());

    await waitFor(() => expect(result.current.items[0]?.name).toBe("local.documents.write"));
    expect(client.list).toHaveBeenLastCalledWith({ query: "write", limit: 50 });
  });

  it("uses the source filter when an explicit search starts", async () => {
    client.list
      .mockResolvedValueOnce(page([summary("local.documents.read")]))
      .mockResolvedValueOnce(page([summary("remote.documents.read", "remote.documents")]));
    const { result } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.phase).toBe("ready"));

    act(() => result.current.setSourceId("remote.documents"));
    act(() => result.current.search());

    await waitFor(() => expect(result.current.items[0]?.sourceId).toBe("remote.documents"));
    expect(client.list).toHaveBeenLastCalledWith({
      sourceId: "remote.documents",
      limit: 50,
    });
    expect(result.current.selected).toBeNull();
  });

  it("reloads and clears selection when the connected target changes", async () => {
    client.list
      .mockResolvedValueOnce(page([summary("local.documents.read")]))
      .mockResolvedValueOnce(page([summary("remote.documents.read", "remote.documents")]));
    client.inspect.mockResolvedValue(detail("local.documents.read"));
    const renders: Array<{ items: ReadonlyArray<CapabilitySummary>; selected: CapabilityDetail | null }> = [];
    const { result, rerender } = renderHook(() => {
      const current = useCapabilityDiscovery();
      renders.push({ items: current.items, selected: current.selected });
      return current;
    });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => result.current.inspect("local.documents.read"));
    await waitFor(() => expect(result.current.selected?.name).toBe("local.documents.read"));

    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://new-workflow.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: {} as ConsoleReadExecutor,
      writeExecutor: null,
    });
    const renderCountBeforeTargetChange = renders.length;
    rerender();

    expect(renders[renderCountBeforeTargetChange]?.items).toEqual([]);
    expect(renders[renderCountBeforeTargetChange]?.selected).toBeNull();
    await waitFor(() => expect(result.current.items[0]?.sourceId).toBe("remote.documents"));
    expect(result.current.selected).toBeNull();
    expect(client.list).toHaveBeenLastCalledWith({ limit: 50 });
  });

  it("reconnects with applied filters instead of unsubmitted filter edits", async () => {
    client.list
      .mockResolvedValueOnce(page([summary("local.documents.read")]))
      .mockResolvedValue(page([summary("remote.documents.read", "remote.documents")]));
    const { result, rerender } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.phase).toBe("ready"));

    act(() => result.current.setQuery("unsubmitted-query"));
    act(() => result.current.setSourceId("unsubmitted-source"));

    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://reconnected-workflow.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: {} as ConsoleReadExecutor,
      writeExecutor: null,
    });
    rerender();

    await waitFor(() => expect(result.current.items[0]?.sourceId).toBe("remote.documents"));
    expect(client.list).toHaveBeenLastCalledWith({ limit: 50 });
  });

  it("appends the next page without duplicating capability names", async () => {
    client.list
      .mockResolvedValueOnce(page([summary("local.documents.read")], "page-2"))
      .mockResolvedValueOnce(
        page([
          summary("local.documents.read"),
          summary("local.documents.write"),
          summary("local.documents.write"),
        ]),
      );
    const { result } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.nextCursor).toBe("page-2"));

    act(() => result.current.loadMore());

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(client.list).toHaveBeenLastCalledWith({ cursor: "page-2", limit: 50 });
    expect(result.current.items.map((item) => item.name)).toEqual([
      "local.documents.read",
      "local.documents.write",
    ]);
  });

  it("uses the applied filters when loading more after draft edits", async () => {
    client.list
      .mockResolvedValueOnce(page([summary("local.documents.read")], "page-2"))
      .mockResolvedValueOnce(page([summary("local.documents.write")]));
    const { result } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.nextCursor).toBe("page-2"));

    act(() => result.current.setQuery("draft-query"));
    act(() => result.current.setSourceId("draft-source"));
    act(() => result.current.loadMore());

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(client.list).toHaveBeenLastCalledWith({ cursor: "page-2", limit: 50 });
  });

  it("does not start a second load-more request while the page is pending", async () => {
    const nextPage = deferred<CapabilityPage>();
    client.list.mockResolvedValueOnce(page([summary("local.documents.read")], "page-2"));
    client.list.mockReturnValueOnce(nextPage.promise);
    const { result } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.nextCursor).toBe("page-2"));

    act(() => result.current.loadMore());
    act(() => result.current.loadMore());

    expect(client.list).toHaveBeenCalledTimes(2);
    nextPage.resolve(page([summary("local.documents.write")]));
    await waitFor(() => expect(result.current.items).toHaveLength(2));
  });

  it("loads the selected capability detail", async () => {
    client.list.mockResolvedValue(page([summary("local.documents.read")]));
    client.inspect.mockResolvedValue(detail("local.documents.read"));
    const { result } = renderHook(() => useCapabilityDiscovery());
    await waitFor(() => expect(result.current.phase).toBe("ready"));

    act(() => result.current.inspect("local.documents.read"));

    await waitFor(() => expect(result.current.selected?.name).toBe("local.documents.read"));
    expect(client.inspect).toHaveBeenCalledWith("local.documents.read");
  });

  it("surfaces malformed capability results as an error phase", async () => {
    client.list.mockRejectedValue(new Error("CapabilityPage is malformed"));

    const { result } = renderHook(() => useCapabilityDiscovery());

    await waitFor(() => expect(result.current.phase).toBe("error"));

    expect(result.current.message).toBe("CapabilityPage is malformed");
  });

  it("does not create a client or request while disconnected", () => {
    mockedUseConsoleWorkspace.mockReturnValue({
      connection: disconnectedState,
      connectedTarget: null,
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: null,
    });

    const { result } = renderHook(() => useCapabilityDiscovery());

    expect(result.current.phase).toBe("disconnected");
    expect(mockedCreateCapabilityClient).not.toHaveBeenCalled();
    expect(client.list).not.toHaveBeenCalled();
  });

  it("ignores stale list and inspect responses after newer requests", async () => {
    const firstList = deferred<CapabilityPage>();
    const secondList = deferred<CapabilityPage>();
    const firstDetail = deferred<CapabilityDetail>();
    const secondDetail = deferred<CapabilityDetail>();
    client.list.mockReturnValueOnce(firstList.promise).mockReturnValueOnce(secondList.promise);
    client.inspect
      .mockReturnValueOnce(firstDetail.promise)
      .mockReturnValueOnce(secondDetail.promise);
    const { result } = renderHook(() => useCapabilityDiscovery());

    act(() => result.current.setQuery("newer"));
    act(() => result.current.search());
    expect(client.list).toHaveBeenCalledTimes(2);

    firstList.resolve(page([summary("local.stale.list")]));
    secondList.resolve(page([summary("local.current.list")]));
    await waitFor(() => expect(result.current.items[0]?.name).toBe("local.current.list"));

    act(() => result.current.inspect("local.first"));
    act(() => result.current.inspect("local.second"));
    firstDetail.resolve(detail("local.first"));
    secondDetail.resolve(detail("local.second"));

    await waitFor(() => expect(result.current.selected?.name).toBe("local.second"));
  });
});
