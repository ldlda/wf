import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvidenceRecord } from "../app/state.js";
import type { DemoChromePresentation } from "./presentation-demo-chrome.js";
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
    const hiddenRail: DemoChromePresentation = {
      kind: "hidden",
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
        demoRail={hiddenRail}
        retryHealth={vi.fn()}
        showEvidenceReceipt
        inspectEvidence={vi.fn()}
      />,
    );
    const footer = screen.getByRole("contentinfo", { name: /presentation footer/i });
    expect(within(footer).getByText("6 / 14")).toBeInTheDocument();
    expect(within(footer).getByText("3 / 4")).toBeInTheDocument();
    expect(within(footer).getByText(/workflow\.runs\.trace/)).toBeInTheDocument();
  });

  it("hides target status outside the demo arc", () => {
    render(
      <PresentationFooter
        location={{
          kind: "main",
          sceneId: "conclusion",
          beatId: "questions",
          focusPath: [],
        }}
        evidence={[]}
        demoRail={{ kind: "hidden" }}
        retryHealth={vi.fn()}
        showEvidenceReceipt={false}
        inspectEvidence={vi.fn()}
      />,
    );

    const footer = screen.getByRole("contentinfo", { name: /presentation footer/i });
    expect(within(footer).queryByLabelText("presentation evidence mode")).not.toBeInTheDocument();
  });

  it("renders exactly one healthy demo rail for a demo location", () => {
    render(
      <PresentationFooter
        location={{ kind: "main", sceneId: "agent-handoff", beatId: "request", focusPath: [] }}
        evidence={[]}
        demoRail={{
          kind: "action",
          mode: "live",
          label: "Run prepared workflow",
          status: {
            kind: "ready",
            target: "http://127.0.0.1:8765/rpc",
            label: "Live target ready",
            detail: "127.0.0.1:8765",
          },
          canRun: true,
          canRetry: true,
        }}
        retryHealth={vi.fn()}
        showEvidenceReceipt={false}
        inspectEvidence={vi.fn()}
      />,
    );

    expect(screen.getAllByTestId("presentation-demo-rail")).toHaveLength(1);
    expect(screen.getByText("Live target ready")).toBeInTheDocument();
  });
});
