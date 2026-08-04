import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CapabilityDiscoveryController } from "./useCapabilityDiscovery.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";
import { DiscoverRoute } from "./DiscoverRoute.js";

vi.mock("./useCapabilityDiscovery.js", () => ({
  useCapabilityDiscovery: vi.fn(),
}));

const mockedUseCapabilityDiscovery = vi.mocked(useCapabilityDiscovery);

const summary = {
  kind: "node_spec" as const,
  name: "local.documents.read",
  sourceId: "local.documents",
  description: "Read project documents.",
  outcomes: ["ok", "error"],
  inputFields: ["names"],
  outputFields: ["documents"],
};

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

beforeEach(() => mockedUseCapabilityDiscovery.mockReturnValue(controller()));
afterEach(() => cleanup());

describe("DiscoverRoute", () => {
  it("shows the discovery heading and searchable source-filtered controls", () => {
    render(<DiscoverRoute />);

    expect(screen.getByRole("heading", { name: "Discover capabilities" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Search capabilities" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Filter by source" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("renders compact capability rows with contract summary fields", async () => {
    const inspect = vi.fn();
    mockedUseCapabilityDiscovery.mockReturnValue(controller({ inspect }));
    render(<DiscoverRoute />);

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
    render(<DiscoverRoute />);

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
    render(<DiscoverRoute />);

    expect(screen.getByRole("heading", { name: "Input schema" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Output schema" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Wrapper hints" })).toBeInTheDocument();
    expect(screen.getAllByText(/"names"/)).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /add to draft/i })).toBeNull();
  });

  it("shows load more only when the controller has a next cursor", async () => {
    const loadMore = vi.fn();
    mockedUseCapabilityDiscovery.mockReturnValue(
      controller({ nextCursor: "page-2", loadMore }),
    );
    render(<DiscoverRoute />);

    await userEvent.click(screen.getByRole("button", { name: "Load more capabilities" }));
    expect(loadMore).toHaveBeenCalledOnce();

    cleanup();
    mockedUseCapabilityDiscovery.mockReturnValue(controller());
    render(<DiscoverRoute />);
    expect(screen.queryByRole("button", { name: "Load more capabilities" })).toBeNull();
  });
});
