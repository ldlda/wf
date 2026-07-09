import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvidenceRecord } from "../app/state.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";
import { PresentationFooter } from "./PresentationFooter.js";

afterEach(() => cleanup());

describe("PresentationFooter", () => {
  it("combines scene progress and evidence provenance", () => {
    const evidence: EvidenceRecord = {
      id: "trace",
      operation: "workflow.runs.trace",
      label: "Inspect trace",
      equivalentCli: "uv run wf run trace run_demo",
      request: { run_id: "run_demo" },
      response: { result: { status: "completed" } },
      durationMs: 34,
    };
    const replayHealth: PresentationTargetHealth = {
      kind: "replay",
      label: "Replay evidence",
      detail: "reviewed recording",
    };
    render(
      <PresentationFooter
        location={{
          kind: "main",
          sceneId: "architecture",
          beatId: "runtime",
          focusPath: [],
        }}
        evidence={[evidence]}
        targetStatus={replayHealth}
        showEvidenceReceipt
        inspectEvidence={vi.fn()}
      />,
    );
    const footer = screen.getByRole("contentinfo", { name: /presentation footer/i });
    expect(within(footer).getByText("6 / 14")).toBeInTheDocument();
    expect(within(footer).getByText("3 / 4")).toBeInTheDocument();
    expect(within(footer).getByText(/workflow\.runs\.trace/)).toBeInTheDocument();
  });
});
