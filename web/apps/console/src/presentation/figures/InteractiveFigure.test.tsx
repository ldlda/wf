import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, afterAll, describe, expect, it, vi } from "vitest";
import type { FigureCatalogDefinition } from "./model.js";
import { InteractiveFigure } from "./InteractiveFigure.js";

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  globalThis.DOMRect = {
    fromRect: () => ({
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      toJSON() {},
    }),
  } as unknown as typeof DOMRect;
});

afterAll(() => {
  delete (globalThis as Record<string, unknown>).ResizeObserver;
  delete (globalThis as Record<string, unknown>).DOMRect;
});

const validCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [
    {
      id: "architecture-overview",
      title: "Architecture",
      layout: { kind: "layered" },
      nodes: [
        { id: "client", label: "Client operations", summary: "CLI callers", kind: "actor" },
        { id: "runtime", label: "Runtime & providers", summary: "WorkflowServer", kind: "runtime", childFigureId: "runtime-detail" },
        {
          id: "leaf",
          label: "Leaf node",
          summary: "Non-expandable",
          kind: "artifact",
          evidence: {
            label: "Stored fact",
            title: "Leaf evidence",
            body: "The graph remains visible while this factual detail is inspected.",
            facts: [{ label: "Pointer", value: "docs/example.md" }],
          },
        },
      ],
      edges: [{ id: "e1", from: "client", to: "runtime", label: "calls" }],
    },
    {
      id: "runtime-detail",
      title: "Runtime detail",
      layout: { kind: "layered" },
      nodes: [
        { id: "providers", label: "Configured providers", summary: "Built-in and external", kind: "runtime", childFigureId: "provider-detail" },
        { id: "leaf2", label: "Leaf detail", summary: "Static detail", kind: "artifact" },
      ],
      edges: [{ id: "e2", from: "providers", to: "leaf2", label: "uses" }],
    },
    {
      id: "provider-detail",
      title: "Provider detail",
      layout: { kind: "layered" },
      nodes: [
        { id: "mcp", label: "MCP providers", summary: "Model Context Protocol", kind: "runtime" },
        { id: "python", label: "Python provider", summary: "Trusted in-process", kind: "runtime" },
      ],
      edges: [{ id: "e3", from: "mcp", to: "python", label: "delegates" }],
    },
  ],
};

const figureNode = (id: string) => screen.getByTestId(`figure-node-${id}`);

const renderFigure = (overrides: Partial<React.ComponentProps<typeof InteractiveFigure>> = {}) => {
  const onFocusPathChange = overrides.onFocusPathChange ?? vi.fn();
  const { onFocusPathChange: _, ...restOverrides } = overrides;
  return {
    onFocusPathChange,
    ...render(
      <InteractiveFigure
        catalog={restOverrides.catalog ?? validCatalog}
        focusPath={restOverrides.focusPath ?? []}
        activeNodeId={restOverrides.activeNodeId ?? null}
        onFocusPathChange={onFocusPathChange}
        motionDisabled={restOverrides.motionDisabled ?? false}
        size={restOverrides.size ?? "standard"}
      />,
    ),
  };
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("InteractiveFigure", () => {
  it("renders conceptual labels and hides evidence pointers by default", () => {
    renderFigure({ focusPath: [] });
    expect(figureNode("runtime")).toBeInTheDocument();
    expect(figureNode("runtime")).toHaveTextContent("Runtime & providers");
    expect(screen.queryByText(/docs\/source_architecture\.md/i)).not.toBeInTheDocument();
  });

  it("renders within a React Flow container for edge support", () => {
    const { container } = renderFigure({ focusPath: [] });
    const rfWrapper = screen.getByTestId("rf__wrapper");
    expect(rfWrapper).toBeInTheDocument();
    expect(rfWrapper.querySelector("[class*='react-flow']")).toBeInTheDocument();
    expect(container.querySelector(".react-flow__handle-top")).toBeInTheDocument();
    expect(container.querySelector(".react-flow__handle-bottom")).toBeInTheDocument();
  });

  it("keeps one node tabbable when no node is marked current", () => {
    renderFigure({ focusPath: [], activeNodeId: null });

    expect(figureNode("client")).toHaveAttribute("tabindex", "0");
    expect(figureNode("runtime")).toHaveAttribute("tabindex", "-1");
    expect(figureNode("leaf")).toHaveAttribute("tabindex", "-1");
  });

  it("uses left and right handles for flow figures", () => {
    const flowCatalog: FigureCatalogDefinition = {
      ...validCatalog,
      figures: validCatalog.figures.map((figure) =>
        figure.id === validCatalog.rootFigureId
          ? { ...figure, layout: { kind: "flow" as const } }
          : figure,
      ),
    };
    const { container } = renderFigure({ catalog: flowCatalog });
    expect(container.querySelector(".react-flow__handle-left")).toBeInTheDocument();
    expect(container.querySelector(".react-flow__handle-right")).toBeInTheDocument();
  });

  it("expands a child figure by click and Enter", async () => {
    const user = userEvent.setup();
    const { onFocusPathChange } = renderFigure({ focusPath: [], onFocusPathChange: vi.fn() });
    fireEvent.click(figureNode("runtime"));
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime"]);
    figureNode("runtime").focus();
    await user.keyboard("{Enter}");
    expect(onFocusPathChange).toHaveBeenLastCalledWith(["runtime"]);
  });

  it("pops one focus level with Escape and breadcrumb activation", async () => {
    const user = userEvent.setup();
    const { onFocusPathChange } = renderFigure({
      focusPath: ["runtime", "providers"],
      onFocusPathChange: vi.fn(),
    });
    figureNode("mcp").focus();
    await user.keyboard("{Escape}");
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime"]);
    await user.click(screen.getByRole("button", { name: /architecture/i }));
    expect(onFocusPathChange).toHaveBeenLastCalledWith([]);
  });

  it("uses arrow keys inside the figure without bubbling presentation navigation", async () => {
    const user = userEvent.setup();
    const outerKeyDown = vi.fn();
    render(
      <div onKeyDown={outerKeyDown}>
        <InteractiveFigure
          catalog={validCatalog}
          focusPath={[]}
          activeNodeId="client"
          onFocusPathChange={vi.fn()}
          motionDisabled={false}
        />
      </div>,
    );
    figureNode("client").focus();
    await user.keyboard("{ArrowDown}");
    expect(outerKeyDown).not.toHaveBeenCalled();
    expect(figureNode("runtime")).toHaveFocus();
  });

  it("retains all information when motion is disabled", () => {
    renderFigure({ focusPath: ["runtime"], motionDisabled: true });
    expect(screen.getByRole("group", { name: /runtime detail/i })).toHaveAttribute("data-motion", "disabled");
    expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
  });

  it("marks stage figures as horizontally navigable presentation maps", () => {
    renderFigure({ focusPath: [], size: "stage" });
    const figure = screen.getByRole("group", { name: /architecture/i });
    expect(figure).toHaveAttribute("data-figure-size", "stage");
    expect(figure).toHaveAttribute("data-figure-layout", "layered");
    expect(figure).toHaveAttribute("data-figure-focus-level", "0");
    expect(figure.querySelector(".interactive-figure__canvas")).toBeInTheDocument();
  });

  it("opens leaf evidence without replacing the figure", () => {
    renderFigure({ size: "stage" });
    fireEvent.click(figureNode("leaf"));
    expect(screen.getByRole("region", { name: /leaf node evidence/i })).toHaveTextContent("Leaf evidence");
    expect(screen.getByRole("region", { name: /leaf node evidence/i })).toHaveTextContent("docs/example.md");
    expect(figureNode("leaf")).toBeInTheDocument();
  });

  it("enables pan and zoom on the root architecture figure", () => {
    renderFigure({ focusPath: [], size: "stage" });

    expect(screen.getByRole("group", { name: /architecture/i })).toHaveAttribute(
      "data-pan-zoom",
      "enabled",
    );
  });

  it("enables pan and zoom inspection for focused stage figures", () => {
    renderFigure({ focusPath: ["runtime"], size: "stage" });

    expect(screen.getByRole("group", { name: /runtime detail/i })).toHaveAttribute(
      "data-pan-zoom",
      "enabled",
    );
    expect(screen.getByRole("group", { name: /runtime detail/i })).toHaveAttribute("data-figure-focus-level", "1");
  });

  it("resets roving focus when focusPath changes", () => {
    const { rerender } = render(
      <InteractiveFigure
        catalog={validCatalog}
        focusPath={[]}
        activeNodeId={null}
        onFocusPathChange={vi.fn()}
        motionDisabled={false}
      />,
    );
    const firstFigureId = screen.getByRole("group", { name: /architecture/i }).getAttribute("data-figure-id");
    rerender(
      <InteractiveFigure
        catalog={validCatalog}
        focusPath={["runtime"]}
        activeNodeId={null}
        onFocusPathChange={vi.fn()}
        motionDisabled={false}
      />,
    );
    const secondFigureId = screen.getByRole("group", { name: /runtime detail/i }).getAttribute("data-figure-id");
    expect(secondFigureId).not.toBe(firstFigureId);
    expect(figureNode("providers")).toBeInTheDocument();
  });

  it("schedules a settled fitView pass for stage figures", () => {
    const requestAnimationFrameSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((callback: FrameRequestCallback) => {
        callback(0);
        return 1;
      });
    const cancelAnimationFrameSpy = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});

    renderFigure({ focusPath: [], size: "stage" });

    expect(requestAnimationFrameSpy).toHaveBeenCalled();
  });
});
