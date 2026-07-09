import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
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
  primeReplayToStage: noop,
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
  options: {
    readonly openEvidence?: () => void;
    readonly approvalActions?: DemoApprovalActions;
  } = {},
) => {
  const openEvidence = options.openEvidence ?? vi.fn();
  const { scene, beat } = requireSceneBeat(sceneId, beatId);
  const rendered = render(
    <DemoWorkflowScene
      scene={scene}
      beat={beat}
      demo={demo}
      selectedNodeId={null}
      selectNode={noop}
      openEvidence={openEvidence}
      approvalActions={options.approvalActions}
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

  it("carries the contract into Scene 10 approval via guided product moment", () => {
    renderBeat("approval", "interrupt-evidence");

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "approval");
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  });

  it("makes the Scene 10 approval contract the primary visual", () => {
    renderBeat("approval", "interrupt-evidence");

    const stage = screen.getByLabelText("demo workflow stage");
    expect(stage).toHaveAttribute("data-demo-layout", "approval");
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  });

  it("marks trace beat as evidence layout via guided product moment", () => {
    renderBeat("trace", "interrupt-evidence");

    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "trace");
  });

  it("renders resume and trace via guided product moment", () => {
    const { unmount } = renderBeat("resume", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "resume");
    unmount();

    renderBeat("trace", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "trace");
  });

  it("passes run proof into full graph beats", () => {
    const { unmount } = renderBeat("graph");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("5 workflow nodes");
    unmount();

    renderBeat("output", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "output");
  });

  it("marks outcome-panel layouts via guided product moment", () => {
    renderBeat("resume", "interrupt-evidence");

    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "operation");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "resume");
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

  it("uses compact graph context for interrupt-focused beats", () => {
    const interrupt = renderBeat("interrupt");
    expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
    interrupt.unmount();

    renderBeat("approval", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "approval");
  });

  it("keeps full graph mode for graph beats and guided product moment for output", () => {
    const graph = renderBeat("graph");
    expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "full");
    graph.unmount();

    renderBeat("output", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "output");
  });

  it("keeps approval beat contract via guided product moment", () => {
    renderBeat("approval", "interrupt-evidence");

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "approval");
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  });

  it("wires approval actions into the Scene 10 schema approval surface", () => {
    renderBeat("approval", "interrupt-evidence", {
      approvalActions: {
        state: "ready",
        canSubmit: true,
        canCancel: true,
        submit: vi.fn(async () => {}),
        cancel: vi.fn(async () => {}),
      },
    });

    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("shows a factual decision form for the approval beat instead of raw schema as the primary visual", () => {
    renderBeat("approval", "interrupt-evidence");

    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.getByText("Workflow input")).toBeInTheDocument();
  });

  it("keeps raw resume schema visible only in interrupt preview mode", () => {
    renderBeat("interrupt");
    expect(screen.getByText("Resume schema")).toBeInTheDocument();
    cleanup();

    renderBeat("approval", "interrupt-evidence");
    expect(screen.queryByText("Resume schema")).not.toBeInTheDocument();
  });

  it("adds guided product moment for resume, output, and trace beats", () => {
    const resume = renderBeat("resume", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "resume");
    resume.unmount();

    const output = renderBeat("output", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "output");
    output.unmount();

    renderBeat("trace", "interrupt-evidence");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "trace");
  });
});
