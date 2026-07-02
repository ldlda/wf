import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProtocolEvidence } from "./ProtocolEvidence.js";
import type { EvidenceRecord } from "../app/state.js";

beforeEach(() => {
  cleanup();
});

afterEach(() => {
  cleanup();
});

const makeRecord = (
  overrides: Partial<EvidenceRecord> & { id: string },
): EvidenceRecord => ({
  operation: "workflow.health",
  label: "Health check",
  equivalentCli: "uv run wf status",
  request: { method: "workflow.health" },
  response: { status: "ok" },
  durationMs: 12,
  ...overrides,
});

describe("ProtocolEvidence", () => {
  it("shows empty state when no evidence", () => {
    render(<ProtocolEvidence evidence={[]} />);
    expect(screen.getByTestId("evidence-empty")).toHaveTextContent(
      "No evidence recorded yet.",
    );
  });

  it("lists evidence records as selectable toggles", () => {
    const evidence = [
      makeRecord({ id: "health-1", operation: "workflow.health" }),
      makeRecord({ id: "sources-1", operation: "workflow.sources.list" }),
    ];
    render(<ProtocolEvidence evidence={evidence} />);

    expect(screen.getByTestId("evidence-toggle-health-1")).toBeDefined();
    expect(screen.getByTestId("evidence-toggle-sources-1")).toBeDefined();
  });

  it("expands to show equivalent CLI, request, and response", async () => {
    const user = userEvent.setup();
    const evidence = [
      makeRecord({
        id: "health-1",
        operation: "workflow.health",
        equivalentCli: "uv run wf status",
        request: { jsonrpc: "2.0", method: "workflow.health" },
        response: { status: "ok", storeRoot: "/tmp" },
        durationMs: 8,
      }),
    ];
    render(<ProtocolEvidence evidence={evidence} />);

    await user.click(screen.getByTestId("evidence-toggle-health-1"));

    const detail = screen.getByTestId("evidence-detail-health-1");
    expect(detail).toBeDefined();

    const cliSection = within(detail).getAllByRole("heading", {
      name: "Equivalent CLI",
    });
    expect(cliSection).toHaveLength(1);
    expect(detail.textContent).toContain("uv run wf status");

    const preElements = detail.querySelectorAll("pre code");
    expect(preElements.length).toBeGreaterThanOrEqual(2);
    expect(preElements[0]?.textContent).toContain("uv run wf status");
    expect(preElements[1]?.textContent).toContain("workflow.health");
  });

  it("shows 'No response received.' for null response", async () => {
    const user = userEvent.setup();
    const evidence = [
      makeRecord({ id: "health-1", response: null }),
    ];
    render(<ProtocolEvidence evidence={evidence} />);

    await user.click(screen.getByTestId("evidence-toggle-health-1"));

    const detail = screen.getByTestId("evidence-detail-health-1");
    expect(detail.textContent).toContain("No response received.");
  });

  it("renders evidence through pre/code elements, never HTML", async () => {
    const user = userEvent.setup();
    const evidence = [
      makeRecord({
        id: "health-1",
        request: { html: "<script>alert('xss')</script>" },
        response: null,
      }),
    ];
    render(<ProtocolEvidence evidence={evidence} />);

    await user.click(screen.getByTestId("evidence-toggle-health-1"));

    const detail = screen.getByTestId("evidence-detail-health-1");
    const preCodes = detail.querySelectorAll("pre code");
    expect(preCodes.length).toBeGreaterThanOrEqual(2);
    const requestCode = preCodes[1] as Element;
    expect(requestCode.textContent).toContain("<script>");
    expect(requestCode.innerHTML).not.toContain("<script>");
  });

  it("is keyboard operable with native button", async () => {
    const user = userEvent.setup();
    const evidence = [
      makeRecord({ id: "health-1" }),
    ];
    render(<ProtocolEvidence evidence={evidence} />);

    const toggle = screen.getByTestId("evidence-toggle-health-1");
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.tab();
    await user.keyboard("{Enter}");

    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Enter}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("collapses previous when opening another", async () => {
    const user = userEvent.setup();
    const evidence = [
      makeRecord({ id: "health-1", operation: "workflow.health" }),
      makeRecord({ id: "sources-1", operation: "workflow.sources.list" }),
    ];
    render(<ProtocolEvidence evidence={evidence} />);

    await user.click(screen.getByTestId("evidence-toggle-health-1"));
    expect(screen.getByTestId("evidence-detail-health-1")).toBeDefined();

    await user.click(screen.getByTestId("evidence-toggle-sources-1"));
    expect(screen.getByTestId("evidence-detail-sources-1")).toBeDefined();
    expect(screen.queryByTestId("evidence-detail-health-1")).toBeNull();
  });
});
