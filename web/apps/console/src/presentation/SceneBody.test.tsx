import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { SceneBody } from "./SceneBody.js";
import type { PresentationLocation } from "./storyboard.js";
import { findBeat, findScene } from "./storyboard.js";

const noop = () => {};
const noopAsync = async () => {};
const recording = loadCanonicalDemoRecording();
const demo: DemoTimelineController = {
  state: {
    mode: "replay",
    phase: "review",
    events: recording.events,
    appliedCount: recording.events.length,
    autoplay: false,
    error: null,
  },
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: recording.recordingId,
  canStart: true,
  setMode: noop,
  start: noop,
  pause: noop,
  play: noop,
  next: noopAsync,
  submitSelectedIssues: noopAsync,
  cancelReview: noopAsync,
  restart: noop,
};

afterEach(() => cleanup());

describe("SceneBody", () => {
  it("renders narrative metadata without mounting the demo graph", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );
    expect(screen.getByRole("heading", { name: /Positioning and Related Systems/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/workflow graph/i)).not.toBeInTheDocument();
  });

  it("renders the real workflow graph for demo scenes", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "workflow-demo", beatId: "graph", focusPath: [] };
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );
    expect(screen.getByLabelText(/workflow graph/i)).toBeInTheDocument();
  });

  it("opens thesis Q&A branches from the thesis scene", async () => {
    const user = userEvent.setup();
    const location: PresentationLocation = { kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] };
    const openDiscussion = vi.fn();

    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={openDiscussion}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    await user.click(screen.getByRole("button", { name: /where is the ai agent/i }));

    expect(openDiscussion).toHaveBeenCalledWith("where-is-ai-agent");
  });

  it("opens a scene discussion branch from the scene body", async () => {
    const user = userEvent.setup();
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
    const openDiscussion = vi.fn();
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={openDiscussion}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    await user.click(screen.getByRole("button", { name: /hosted automation/i }));

    expect(openDiscussion).toHaveBeenCalledWith("hosted-automation");
  });

  it("renders Scene 3 as a full positioning map", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    const map = screen.getByLabelText("positioning map");
    expect(map).toHaveAttribute("data-positioning-active-region", "landscape");
    const withinMap = within(map);
    expect(withinMap.getByText("Tool loops")).toBeInTheDocument();
    expect(withinMap.getByText("Generated scripts")).toBeInTheDocument();
    expect(withinMap.getByText("lda.chat")).toBeInTheDocument();
    expect(withinMap.getByText("Agent graphs")).toBeInTheDocument();
    expect(withinMap.getByText("MCP")).toBeInTheDocument();
  });

  it("emphasizes lda.chat in the positioning beat", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "lda-position", focusPath: [] };
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    const substrate = screen.getByText("lda.chat").closest("[data-positioning-role='substrate']");
    expect(substrate).toHaveAttribute("data-positioning-active", "true");
    expect(screen.getByLabelText("positioning map")).toHaveAttribute("data-positioning-active-region", "lda");
  });

  it("renders Scene 7 as an agent authoring loop with beat-specific emphasis", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "authoring", beatId: "diagnose", focusPath: [] };
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    const loop = screen.getByLabelText("agent authoring loop");
    expect(loop).toHaveAttribute("data-readable-surface", "dark");
    expect(loop).toHaveAttribute("data-active-stage", "diagnose");
    expect(screen.getByText("Discover capability")).toBeInTheDocument();
    expect(screen.getByText("Author draft")).toBeInTheDocument();
    expect(screen.getByText("Validate and diagnose").closest("[data-authoring-active]")).toHaveAttribute("data-authoring-active", "true");
    expect(screen.getByText("Validate and diagnose").closest(".scene-body__authoring-node"))
      .toHaveAttribute("data-readable-surface", "dark");
    expect(screen.getByText("Repair")).toBeInTheDocument();
    expect(screen.getByText("Compile or save")).toBeInTheDocument();
  });
});
