import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { DemoWorkflowScene } from "./DemoWorkflowScene.js";
import { findBeat, findScene } from "./storyboard.js";

afterEach(() => cleanup());

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

const requireSceneBeat = (sceneId: string, beatId: string) => {
  const scene = findScene(sceneId);
  const beat = findBeat(sceneId, beatId);
  if (!scene || !beat) throw new Error(`missing storyboard fixture ${sceneId}/${beatId}`);
  return { scene, beat };
};

const renderBeat = (
  beatId: string,
  sceneId = "workflow-demo",
  openEvidence = vi.fn(),
) => {
  const { scene, beat } = requireSceneBeat(sceneId, beatId);
  const rendered = render(
    <DemoWorkflowScene
      scene={scene}
      beat={beat}
      demo={demo}
      selectedNodeId={null}
      selectNode={noop}
      openEvidence={openEvidence}
    />,
  );
  return { ...rendered, openEvidence };
};

describe("DemoWorkflowScene", () => {
  it("gives the start operation the stage and opens raw evidence on demand", async () => {
    const { openEvidence } = renderBeat("operation");

    expect(screen.getByLabelText("workflow.runs.start operation")).toBeInTheDocument();
    expect(screen.queryByLabelText("workflow graph")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /view raw evidence/i }));
    expect(openEvidence).toHaveBeenCalledOnce();
  });

  it("keeps the run receipt visible when the graph takes over", () => {
    renderBeat("graph");

    expect(screen.getByLabelText("workflow.runs.start execution receipt")).toBeInTheDocument();
    expect(screen.getAllByText("run_recorded_lda_report").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText("workflow graph")).toBeInTheDocument();
  });

  it("renders the canonical typed interrupt contract", () => {
    renderBeat("interrupt");

    const contract = screen.getByLabelText("typed interrupt contract");
    expect(contract).toHaveTextContent("issue_review");
    expect(contract).toHaveTextContent("submitted / cancelled");
    expect(contract).toHaveTextContent('"type": "object"');
    expect(contract).toHaveTextContent("run_recorded_lda_report");
  });

  it("carries the same graph and contract into Scene 10 approval", () => {
    renderBeat("approval", "interrupt-evidence");

    expect(screen.getByLabelText("workflow graph")).toBeInTheDocument();
    expect(screen.getByLabelText("typed interrupt contract")).toHaveTextContent(
      "run_recorded_lda_report",
    );
    expect(screen.getByRole("button", { name: /issue review/i })).toHaveAttribute(
      "data-execution-state",
      "current",
    );
  });

  it("makes the Scene 10 approval contract the primary visual", () => {
    renderBeat("approval", "interrupt-evidence");

    const stage = screen.getByLabelText("demo workflow stage");
    expect(stage).toHaveAttribute("data-demo-layout", "approval");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveAttribute("data-hero", "true");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveTextContent("Operator decision");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveTextContent("Resume outcomes");
    expect(screen.getByLabelText("workflow graph")).toBeInTheDocument();
  });

  it("marks trace beat as evidence layout", () => {
    renderBeat("trace", "interrupt-evidence");

    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "evidence");
    expect(screen.getByLabelText("workflow.runs.trace operation")).toBeInTheDocument();
  });

  it("renders resume and trace operations as expanded evidence summaries", () => {
    const { unmount } = renderBeat("resume", "interrupt-evidence");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
    unmount();

    renderBeat("trace", "interrupt-evidence");
    expect(screen.getByLabelText("workflow.runs.trace operation")).toBeInTheDocument();
  });

  it("passes run proof into graph-heavy beats", () => {
    const { unmount } = renderBeat("graph");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("5 workflow nodes");
    unmount();

    renderBeat("approval", "interrupt-evidence");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("JSON-RPC evidence");
  });

  it("marks outcome-panel layouts so CSS can clear the receipt row", () => {
    renderBeat("approval", "interrupt-evidence");

    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "approval");
    expect(screen.getByLabelText("demo outcome proof")).toBeInTheDocument();
    expect(screen.getByLabelText("workflow.runs.start execution receipt")).toBeInTheDocument();
  });

  it("shows the continuity rail across Scene 9 operation, graph, and interrupt beats", () => {
    const { unmount } = renderBeat("operation");
    expect(screen.getByLabelText("demo continuity")).toHaveTextContent("workflow.runs.start");
    expect(screen.getByLabelText("demo continuity")).toHaveTextContent("Agent request");
    unmount();

    const graph = renderBeat("graph");
    expect(screen.getByLabelText("demo continuity")).toHaveTextContent("typed graph");
    graph.unmount();

    renderBeat("interrupt");
    expect(screen.getByLabelText("demo continuity")).toHaveTextContent("issue_review");
  });

  it("adds outcome proof to approval, resume, output, and trace beats", () => {
    const approval = renderBeat("approval", "interrupt-evidence");
    expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("schema-backed");
    approval.unmount();

    const resume = renderBeat("resume", "interrupt-evidence");
    expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("Same persisted run");
    resume.unmount();

    const output = renderBeat("output", "interrupt-evidence");
    expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("Report markdown");
    output.unmount();

    renderBeat("trace", "interrupt-evidence");
    expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("Trace frames");
  });
});
