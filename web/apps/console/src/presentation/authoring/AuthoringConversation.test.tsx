import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AuthoringConversation } from "./AuthoringConversation.js";

afterEach(cleanup);

describe("AuthoringConversation", () => {
  it("renders a full prepared chat with real workflow tool calls", () => {
    render(
      <AuthoringConversation
        throughPhase="deployment"
        activePhase="deployment"
        surface="stage"
      />,
    );

    expect(screen.getByRole("log", { name: "prepared authoring conversation" }))
      .toHaveAttribute("data-surface", "stage");
    expect(screen.getAllByText(/workflow\.deployments\.save/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/deployment/i).length).toBeGreaterThan(0);
  });

  it("opens only the beat-synchronized tool group in dock mode", () => {
    render(
      <AuthoringConversation
        throughPhase="validate"
        activePhase="validate"
        surface="dock"
      />,
    );

    const log = screen.getByRole("log", { name: "prepared authoring conversation" });
    expect(log).toHaveAttribute("data-surface", "dock");
    expect(screen.getByRole("button", { name: /validate.*2 tool calls/i }))
      .toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /draft.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "false");
  });
});
