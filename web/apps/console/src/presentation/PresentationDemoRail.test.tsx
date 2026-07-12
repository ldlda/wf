import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DemoChromePresentation } from "./presentation-demo-chrome.js";
import { PresentationDemoRail } from "./PresentationDemoRail.js";

afterEach(() => cleanup());

const readyAction: DemoChromePresentation = {
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
};

describe("PresentationDemoRail", () => {
  it("renders no content when demo chrome is hidden", () => {
    const { container } = render(
      <PresentationDemoRail presentation={{ kind: "hidden" }} retryHealth={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders the target badge and runs a healthy live action", () => {
    const runPreparedWorkflow = vi.fn(async () => {});
    render(
      <PresentationDemoRail
        presentation={readyAction}
        runPreparedWorkflow={runPreparedWorkflow}
        retryHealth={vi.fn()}
      />,
    );

    const rail = screen.getByTestId("presentation-demo-rail");
    expect(within(rail).getByLabelText("presentation evidence mode")).toBeInTheDocument();
    fireEvent.click(within(rail).getByRole("button", { name: "Run prepared workflow" }));
    expect(runPreparedWorkflow).toHaveBeenCalledWith("live");
  });

  it("uses replay action and retry when live health has failed", () => {
    const retryHealth = vi.fn();
    render(
      <PresentationDemoRail
        presentation={{
          ...readyAction,
          mode: "replay",
          label: "Play replay walkthrough",
          status: {
            kind: "failed",
            target: "http://127.0.0.1:8765/rpc",
            label: "Replay fallback",
            detail: "connection refused",
          },
        }}
        retryHealth={retryHealth}
      />,
    );

    const rail = screen.getByTestId("presentation-demo-rail");
    expect(within(rail).getByRole("button", { name: "Play replay walkthrough" })).toBeInTheDocument();
    fireEvent.click(within(rail).getByRole("button", { name: "Retry live service" }));
    expect(retryHealth).toHaveBeenCalledOnce();
  });

  it.each([
    ["running", "Running workflow..."],
    ["paused", "Run paused - review required"],
    ["resuming", "Resuming workflow..."],
    ["completed", "Run complete"],
  ] as const)("renders %s as status content without a disabled run button", (kind, label) => {
    render(
      <PresentationDemoRail
        presentation={{ kind, label } as DemoChromePresentation}
        retryHealth={vi.fn()}
      />,
    );

    const rail = screen.getByTestId("presentation-demo-rail");
    expect(within(rail).getByRole("status")).toHaveTextContent(label);
    expect(within(rail).queryByRole("button")).not.toBeInTheDocument();
  });
});
