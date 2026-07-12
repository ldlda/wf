import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { OpeningThesisScene } from "./OpeningThesisScene.js";

const thesisScene = findScene("thesis")!;

afterEach(() => cleanup());

describe("OpeningThesisScene", () => {
  it("introduces the agent-shaped product goal", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "title")!} />);

    const opening = screen.getByRole("region", { name: /thesis opening/i });
    expect(opening).toHaveAttribute("data-opening-focus", "title");
    expect(opening).toHaveAttribute("data-presentation-surface", "editorial");
    expect(screen.getByRole("heading", { name: /An AI agent for workspace automation/i }).parentElement)
      .toHaveAttribute("data-visual-role", "title-hero");
    expect(screen.getByRole("heading", { name: /Design and Implementation of lda\.chat/i })).toBeInTheDocument();
    expect(screen.getByText(/AI agent for workspace automation is the product goal/i)).toBeInTheDocument();
    expect(screen.getByText(/implemented contribution.*typed workflow substrate/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /An AI agent for workspace automation/i })).toBeInTheDocument();
    const roles = screen.getByRole("group", { name: "AI agent roles" });
    expect(roles).toHaveClass("opening-thesis__agent-system");
    expect(roles.querySelectorAll("[data-concept-emphasis]")).toHaveLength(3);
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("Tool surface")).toBeInTheDocument();
    expect(screen.getByText("Runner / platform")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Thesis" })).not.toBeInTheDocument();
    expect(screen.queryByText("Decomposed")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Planner icon/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Tool surface icon/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Runner \/ platform icon/i })).toBeInTheDocument();
  });

  it("identifies runner and platform as the implemented contribution", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "substrate")!} />);

    const opening = screen.getByRole("region", { name: /thesis opening/i });
    expect(opening).toHaveAttribute("data-opening-focus", "contribution");
    expect(screen.getByText("Codex, Claude, OpenCode")).toBeInTheDocument();
    expect(screen.getByText("CLI, MCP, JSON-RPC")).toBeInTheDocument();
    expect(screen.getByText("Implemented contribution")).toBeInTheDocument();
    expect(screen.getByText("Lifecycle, validation, records, traces, and interrupt/resume")).toBeInTheDocument();
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("Tool surface")).toBeInTheDocument();
    expect(screen.getByText("Runner / platform")).toBeInTheDocument();
    expect(screen.queryByText("wf")).not.toBeInTheDocument();
  });
});
