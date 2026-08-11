import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvidenceRecord } from "../app/state.js";
import { EvidenceLedger } from "./EvidenceLedger.js";

const record: EvidenceRecord = {
  id: "health-0",
  target: "http://console.test/rpc",
  operation: "workflow.health",
  label: "Health check",
  equivalentCli: "uv run wf status",
  request: { target: "console" },
  response: { status: "ok" },
  durationMs: 11,
};

describe("EvidenceLedger", () => {
  it("renders each operation as a collapsed detail row with its receipt fields", () => {
    render(<EvidenceLedger records={[record]} />);

    const row = screen.getByRole("group", { name: "Health check" });
    expect(row.tagName).toBe("DETAILS");
    expect(row).not.toHaveAttribute("open");
    expect(row).toHaveTextContent("workflow.health");
    expect(row).toHaveTextContent("11ms");
    expect(row).toHaveTextContent("uv run wf status");
    expect(row).toHaveTextContent('"target": "console"');
    expect(row).toHaveTextContent('"status": "ok"');
  });

  it("renders a useful empty state", () => {
    render(<EvidenceLedger records={[]} />);

    expect(screen.getByText("No operation evidence yet.")).toBeInTheDocument();
  });
});
