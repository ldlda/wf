import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FigureCatalogDefinition } from "./model.js";
import { InteractiveFigure } from "./InteractiveFigure.js";

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
        { id: "leaf", label: "Leaf node", summary: "Non-expandable", kind: "artifact" },
      ],
      edges: [{ id: "e1", from: "client", to: "runtime" }],
    },
    {
      id: "runtime-detail",
      title: "Runtime detail",
      layout: { kind: "layered" },
      nodes: [
        { id: "providers", label: "Configured providers", summary: "Built-in and external", kind: "runtime", childFigureId: "provider-detail" },
        { id: "leaf2", label: "Leaf detail", summary: "Static detail", kind: "artifact" },
      ],
      edges: [{ id: "e2", from: "providers", to: "leaf2" }],
    },
    {
      id: "provider-detail",
      title: "Provider detail",
      layout: { kind: "layered" },
      nodes: [
        { id: "mcp", label: "MCP providers", summary: "Model Context Protocol", kind: "runtime" },
        { id: "python", label: "Python provider", summary: "Trusted in-process", kind: "runtime" },
      ],
      edges: [{ id: "e3", from: "mcp", to: "python" }],
    },
  ],
};

const renderFigure = (overrides: Partial<React.ComponentProps<typeof InteractiveFigure>> = {}) => {
  const onFocusPathChange = overrides.onFocusPathChange ?? vi.fn();
  const { onFocusPathChange: _, ...restOverrides } = overrides;
  return {
    onFocusPathChange,
    ...render(
      <InteractiveFigure
        catalog={validCatalog}
        focusPath={restOverrides.focusPath ?? []}
        activeNodeId={restOverrides.activeNodeId ?? null}
        onFocusPathChange={onFocusPathChange}
        motionDisabled={restOverrides.motionDisabled ?? false}
      />,
    ),
  };
};

afterEach(() => cleanup());

describe("InteractiveFigure", () => {
  it("renders conceptual labels and hides evidence pointers by default", () => {
    renderFigure({ focusPath: [] });
    expect(screen.getByRole("button", { name: /runtime & providers.*expand/i })).toBeInTheDocument();
    expect(screen.queryByText(/docs\/source_architecture\.md/i)).not.toBeInTheDocument();
  });

  it("expands a child figure by click and Enter", async () => {
    const user = userEvent.setup();
    const { onFocusPathChange } = renderFigure({ focusPath: [], onFocusPathChange: vi.fn() });
    await user.click(screen.getByRole("button", { name: /runtime & providers/i }));
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime"]);
    screen.getByRole("button", { name: /runtime & providers/i }).focus();
    await user.keyboard("{Enter}");
    expect(onFocusPathChange).toHaveBeenLastCalledWith(["runtime"]);
  });

  it("pops one focus level with Escape and breadcrumb activation", async () => {
    const user = userEvent.setup();
    const { onFocusPathChange } = renderFigure({
      focusPath: ["runtime", "providers"],
      onFocusPathChange: vi.fn(),
    });
    screen.getByRole("button", { name: /configured providers/i }).focus();
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
    screen.getByRole("button", { name: /client operations/i }).focus();
    await user.keyboard("{ArrowDown}");
    expect(outerKeyDown).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /runtime & providers/i })).toHaveFocus();
  });

  it("retains all information when motion is disabled", () => {
    renderFigure({ focusPath: ["runtime"], motionDisabled: true });
    expect(screen.getByRole("group", { name: /runtime detail/i })).toHaveAttribute("data-motion", "disabled");
    expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
  });
});
