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

const renderArchitecture = (overrides: Partial<React.ComponentProps<typeof ArchitectureScene>> = {}) => {
  const onFocusPathChange = overrides.onFocusPathChange ?? vi.fn();
  return {
    onFocusPathChange,
    ...render(
      <ArchitectureScene
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
  it("renders the overview and expands Runtime & providers", async () => {
    const user = userEvent.setup();
    const onFocusPathChange = vi.fn();
    renderArchitecture({ focusPath: [], onFocusPathChange });
    expect(screen.getByRole("heading", { name: /architecture/i })).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("figure-node-runtime-providers"));
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime-providers"]);
  });

  it("renders a directly linked nested provider view", () => {
    renderArchitecture({
      focusPath: ["runtime-providers", "configured-providers"],
    });
    expect(screen.getByRole("group", { name: /configured providers/i })).toBeInTheDocument();
    expect(screen.getByText("MCP sources")).toBeInTheDocument();
    expect(screen.getByText("Python sources")).toBeInTheDocument();
  });
});
