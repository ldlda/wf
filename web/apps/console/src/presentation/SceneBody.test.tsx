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
  primeReplayToStage: noop,
};

afterEach(() => cleanup());

describe("SceneBody", () => {
  it("renders Scene 1 as an opening decomposition visual", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "thesis", beatId: "substrate", focusPath: [] };

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

    expect(screen.getByLabelText("AI agent decomposition")).toBeInTheDocument();
    expect(screen.getByText("submitted substrate")).toBeInTheDocument();
    expect(screen.getByText("Typed · Durable · Inspectable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /where is the ai agent/i })).toBeInTheDocument();
  });

  it("renders Scene 2 as chat tool loop versus reusable automation", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "problem", beatId: "missing-contracts", focusPath: [] };

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

    expect(screen.getByLabelText("chat tool loop versus reusable automation")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /one-off chat and tool transcript/i })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /durable workflow blueprint/i })).toBeInTheDocument();
    expect(screen.queryByText("Draft")).not.toBeInTheDocument();
    expect(screen.queryByText("Artifact")).not.toBeInTheDocument();
    expect(screen.queryByText("Deployment")).not.toBeInTheDocument();
  });

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
    const location: PresentationLocation = { kind: "main", sceneId: "run-from-deployment", beatId: "graph", focusPath: [] };
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
    expect(screen.getByRole("group", { name: "workflow graph" })).toBeInTheDocument();
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

  it("renders Scene 4 as a planner runtime boundary", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "planner-runtime", beatId: "boundary", focusPath: [] };
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

    const boundary = screen.getByLabelText("planner runtime boundary");
    expect(boundary).toHaveAttribute("data-boundary-active", "boundary");
    const withinBoundary = within(boundary);
    expect(withinBoundary.getByText("Planner")).toBeInTheDocument();
    expect(withinBoundary.getByText("Runtime")).toBeInTheDocument();
    expect(withinBoundary.getByText(/CLI/)).toBeInTheDocument();
    expect(withinBoundary.getByText(/JSON-RPC/)).toBeInTheDocument();
  });

  it("renders Scene 5 as a full workflow lifecycle rail", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "lifecycle", beatId: "deployment", focusPath: [] };
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

    const rail = screen.getByLabelText("workflow lifecycle rail");
    expect(rail).toHaveAttribute("data-lifecycle-active-stage", "deployment");
    const withinRail = within(rail);
    expect(withinRail.getByText("Draft")).toBeInTheDocument();
    expect(withinRail.getByText("Artifact")).toBeInTheDocument();
    expect(withinRail.getByText("Deployment")).toBeInTheDocument();
    expect(withinRail.getByText("Run")).toBeInTheDocument();
    expect(withinRail.getByText("Source binding")).toBeInTheDocument();
  });

  it("updates the lifecycle explanation with the active beat", () => {
    const { rerender } = render(
      <SceneBody
        location={{ kind: "main", sceneId: "lifecycle", beatId: "draft", focusPath: [] }}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    expect(screen.getByLabelText("current lifecycle state")).toHaveTextContent("Mutable authoring state");

    rerender(
      <SceneBody
        location={{ kind: "main", sceneId: "lifecycle", beatId: "run", focusPath: [] }}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    expect(screen.getByLabelText("current lifecycle state")).toHaveTextContent("Execution record and trace");
  });

  it("marks the planner side active on the planner beat", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "planner-runtime", beatId: "planner", focusPath: [] };
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

    expect(screen.getByLabelText("planner runtime boundary")).toHaveAttribute("data-boundary-active", "planner");
    expect(screen.getByText("Planner").closest("[data-boundary-side='planner']")).toHaveAttribute("data-boundary-emphasis", "active");
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

  it("renders discussion branches as a labelled presenter rail", () => {
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

    const rail = screen.getByLabelText("defense discussion topics");
    expect(rail).toHaveAttribute("data-discussion-rail", "true");
    expect(within(rail).getByText("Defense questions")).toBeInTheDocument();
    expect(within(rail).getByRole("list")).toBeInTheDocument();
    expect(within(rail).getByRole("button", { name: /Hosted automation future-work/i })).toBeInTheDocument();
  });

  it("keeps discussion rail actions wired to branch ids", async () => {
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

    await user.click(screen.getByRole("button", { name: /Hosted automation future-work/i }));

    expect(openDiscussion).toHaveBeenCalledWith("hosted-automation");
  });

  it("renders evidence before discussion links so the chip lane cannot cover evidence text", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
    const { container } = render(
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

    const evidence = container.querySelector(".scene-body__evidence");
    const links = container.querySelector(".scene-body__discussion-links");
    expect(evidence).toBeInTheDocument();
    expect(links).toBeInTheDocument();
    expect(evidence?.compareDocumentPosition(links!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
