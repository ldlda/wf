import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PresentationTruthBadge } from "./PresentationTruthBadge.js";

describe("PresentationTruthBadge", () => {
  it("renders status label and detail", () => {
    render(
      <PresentationTruthBadge
        status={{
          kind: "ready",
          target: "http://127.0.0.1:8765/rpc",
          label: "Live target ready",
          detail: "127.0.0.1:8765",
        }}
      />,
    );

    expect(screen.getByLabelText("presentation evidence mode")).toHaveAttribute("data-status", "ready");
    expect(screen.getByText("Live target ready")).toBeInTheDocument();
    expect(screen.getByText("127.0.0.1:8765")).toBeInTheDocument();
  });
});