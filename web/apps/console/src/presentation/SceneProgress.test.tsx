import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SceneProgress } from "./SceneProgress.js";
import type { MainLocation } from "./storyboard.js";

afterEach(() => cleanup());

describe("SceneProgress", () => {
  it("shows scene and beat position for architecture/runtime", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "architecture",
      beatId: "runtime",
      focusPath: [],
    };

    render(<SceneProgress location={location} />);

    expect(screen.getByText("6 / 12")).toBeInTheDocument();
    expect(screen.getByText("3 / 4")).toBeInTheDocument();
  });

  it("shows scene position for workflow-demo/graph", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "workflow-demo",
      beatId: "graph",
      focusPath: [],
    };

    render(<SceneProgress location={location} />);

    expect(screen.getByText("9 / 12")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
  });

  it("has an accessible label", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "architecture",
      beatId: "runtime",
      focusPath: [],
    };

    render(<SceneProgress location={location} />);

    expect(screen.getByLabelText("scene position")).toBeInTheDocument();
  });
});
