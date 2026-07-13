import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SceneProgress, shouldShowBeatCounter } from "./SceneProgress.js";
import type { MainLocation } from "./storyboard.js";

afterEach(() => cleanup());

describe("SceneProgress", () => {
  it("uses scene metadata for a single-beat counter", () => {
    expect(shouldShowBeatCounter({ alwaysShowBeatCounter: true }, 1)).toBe(true);
    expect(shouldShowBeatCounter({ alwaysShowBeatCounter: false }, 1)).toBe(false);
    expect(shouldShowBeatCounter(undefined, 2)).toBe(true);
  });

  it("shows scene and beat position for architecture/runtime", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "architecture",
      beatId: "runtime",
      focusPath: [],
    };

    render(<SceneProgress location={location} />);

    expect(screen.getByText("6 / 13")).toBeInTheDocument();
    expect(screen.getByText("4 / 4")).toBeInTheDocument();
  });

  it("shows scene position for run-from-deployment/graph", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "run-from-deployment",
      beatId: "graph",
      focusPath: [],
    };

    render(<SceneProgress location={location} />);

    expect(screen.getByText("9 / 13")).toBeInTheDocument();
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
  });

  it("shows the single Scene 7 beat position", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "agent-handoff",
      beatId: "request",
      focusPath: [],
    };

    render(<SceneProgress location={location} />);

    expect(screen.getByText("7 / 13")).toBeInTheDocument();
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
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
