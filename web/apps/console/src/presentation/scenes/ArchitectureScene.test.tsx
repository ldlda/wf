import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, afterAll, describe, expect, it, vi } from "vitest";
import { ArchitectureScene } from "./ArchitectureScene.js";

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

const mockScene = {
  id: "architecture",
  number: 6,
  title: "Architecture Zoom",
  claimClass: "implemented" as const,
  evidencePointer: "Thesis System Architecture",
  view: "architecture" as const,
  beats: [],
};

const mockBeat = {
  id: "client",
  title: "Client operations",
  caption: "Human and agent clients use the same public lifecycle surface.",
  chatMode: "rail" as const,
  chatTheme: "light" as const,
  evidencePresentation: "hidden" as const,
  figure: { catalogId: "system-architecture", focusPath: [] as readonly string[], activeNodeId: "client-operations" },
};

const renderArchitecture = (overrides: Partial<React.ComponentProps<typeof ArchitectureScene>> = {}) => {
  const onFocusPathChange = overrides.onFocusPathChange ?? vi.fn();
  return {
    onFocusPathChange,
    ...render(
      <ArchitectureScene
        scene={overrides.scene ?? mockScene}
        beat={overrides.beat ?? mockBeat}
        focusPath={overrides.focusPath ?? []}
        activeNodeId={overrides.activeNodeId ?? null}
        onFocusPathChange={onFocusPathChange}
        motionDisabled={overrides.motionDisabled ?? false}
      />,
    ),
  };
};

afterEach(() => cleanup());

describe("ArchitectureScene", () => {
  it("keeps the overview beat neutral so the entire spine remains readable", () => {
    renderArchitecture({
      beat: { ...mockBeat, id: "overview" },
      focusPath: [],
      activeNodeId: null,
    });

    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-architecture-beat", "overview");
    expect(document.querySelector('.figure-node[data-active="true"]')).toBeNull();
  });

  it("renders the architecture spine and expands the capability boundary", () => {
    const onFocusPathChange = vi.fn();
    renderArchitecture({ focusPath: [], onFocusPathChange });
    expect(screen.getByRole("heading", { name: /architecture/i })).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("figure-node-runtime-providers"));
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime-providers"]);
  });

  it("marks the figure as the one primary visual and exposes stable motion contracts", () => {
    renderArchitecture({ focusPath: [] });
    expect(screen.getByRole("group", { name: /architecture spine/i })).toHaveAttribute("data-figure-size", "stage");
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-visual-pass", "architecture-stage");
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-visual-role", "primary");
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-motion", "enabled");
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-architecture-focus", "system");
  });

  it("keeps the architecture heading stable when motion is disabled", () => {
    renderArchitecture({ focusPath: [], motionDisabled: true });
    expect(screen.getByRole("heading", { name: /architecture zoom/i })).toBeInTheDocument();
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-motion", "disabled");
    expect(screen.getByRole("group", { name: /architecture spine/i })).toHaveAttribute("data-motion", "disabled");
  });

  it("exposes the public surface, kernel loop, and lifecycle contracts at the spine", () => {
    renderArchitecture({ focusPath: [] });
    const spine = screen.getByRole("group", { name: /architecture spine/i });
    expect(spine).toHaveTextContent("Front door and transport");
    expect(spine).toHaveTextContent("Workflow API operations");
    expect(spine).toHaveTextContent("WorkflowServer composition");
    expect(spine).toHaveTextContent("wf_core execution loop");
    expect(spine).toHaveTextContent("Lifecycle records");
    expect(spine).toHaveTextContent("Capability inventory");
  });

  it("renders a directly linked nested provider view", () => {
    renderArchitecture({
      focusPath: ["runtime-providers", "configured-providers"],
    });
    expect(screen.getByRole("group", { name: /configured provider boundary/i })).toBeInTheDocument();
    expect(screen.getByText("MCP sources")).toBeInTheDocument();
    expect(screen.getByText("Python sources")).toBeInTheDocument();
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-architecture-focus", "nested");
    expect(screen.getByRole("group", { name: /configured provider boundary/i })).toHaveAttribute("data-figure-focus-level", "2");
  });

  it("marks the current beat as a guided camera focus", () => {
    renderArchitecture({
      beat: { ...mockBeat, id: "api" },
      focusPath: ["application-lifecycle"],
      activeNodeId: "workflow-api-boundary",
    });

    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-architecture-beat", "api");
    expect(screen.getByTestId("figure-node-workflow-api-boundary")).toHaveAttribute("data-active", "true");
  });

  it("highlights the actual NodeDef handler during the NodeUse beat", () => {
    renderArchitecture({
      beat: { ...mockBeat, id: "node-use" },
      focusPath: ["node-use"],
      activeNodeId: "node-def-handler",
    });

    expect(screen.getByTestId("figure-node-node-def-handler")).toHaveAttribute("data-active", "true");
  });

  it("shows the kernel loop and clickable NodeUse sequence as nested figures", () => {
    const onFocusPathChange = vi.fn();
    renderArchitecture({ focusPath: ["core-runtime"], onFocusPathChange });
    expect(screen.getByRole("group", { name: /wf_core execution loop/i })).toHaveTextContent("Step kind");
    fireEvent.click(screen.getByTestId("figure-node-dispatch-step-kind"));
    expect(onFocusPathChange).toHaveBeenCalledWith(["core-runtime", "dispatch-step-kind"]);

    cleanup();
    renderArchitecture({ focusPath: ["core-runtime", "dispatch-step-kind"], onFocusPathChange });
    expect(screen.getByRole("group", { name: /supported step kinds/i })).toHaveTextContent("NodeUse");
    fireEvent.click(screen.getByTestId("figure-node-node-use"));
    expect(onFocusPathChange).toHaveBeenCalledWith(["core-runtime", "dispatch-step-kind", "node-use"]);
  });
});
