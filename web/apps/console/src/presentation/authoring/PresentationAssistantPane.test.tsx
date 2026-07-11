import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PresentationAssistantPane } from "./PresentationAssistantPane.js";

afterEach(cleanup);

describe("PresentationAssistantPane", () => {
  it("renders a persistent prepared replay surface for the current phase", () => {
    render(<PresentationAssistantPane phase="validate" />);

    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /authoring assistant/i })).toBeInTheDocument();
    expect(screen.getByText(/current phase: validate/i)).toBeInTheDocument();
    expect(screen.getByText(/prepared replay only/i)).toBeInTheDocument();
  });

  it("keeps the active tool group synchronized with the phase", () => {
    render(<PresentationAssistantPane phase="artifact" />);

    expect(screen.getByRole("button", { name: /artifact.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /validate.*2 tool calls/i }))
      .toHaveAttribute("aria-expanded", "false");
  });

  it("does not expose a live or run action", () => {
    render(<PresentationAssistantPane phase="deployment" />);

    expect(screen.queryByRole("button", { name: /run|send|execute/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/workflow\.runs\.start/i)).not.toBeInTheDocument();
  });
});
