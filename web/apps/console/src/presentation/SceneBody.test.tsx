import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SceneBody } from "./SceneBody.js";
import type { PresentationLocation } from "./storyboard.js";

const noop = () => {};

afterEach(() => cleanup());

describe("SceneBody", () => {
  it("renders narrative metadata without mounting the demo graph", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape" };
    render(
      <SceneBody
        location={location}
        demo={null as never}
        selectedNodeId={null}
        selectNode={noop}
      />,
    );
    expect(screen.getByRole("heading", { name: /Positioning and Related Systems/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/workflow graph/i)).not.toBeInTheDocument();
  });

  it("renders the real workflow graph for demo scenes", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "workflow-demo", beatId: "graph" };
    render(
      <SceneBody
        location={location}
        demo={null as never}
        selectedNodeId={null}
        selectNode={noop}
      />,
    );
    expect(screen.getByLabelText(/workflow graph/i)).toBeInTheDocument();
  });
});
