import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { OpeningThesisScene } from "./OpeningThesisScene.js";

const thesisScene = findScene("thesis")!;

afterEach(() => cleanup());

describe("OpeningThesisScene", () => {
  it("makes the title boundary the opening focal artifact", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "title")!} />);

    const opening = screen.getByRole("region", { name: /thesis opening/i });
    expect(opening).toHaveAttribute("data-opening-focus", "title");
    expect(opening).toHaveAttribute("data-support-state", "receded");
    expect(screen.getByRole("heading", { name: /Design and Implementation of lda\.chat/i })).toBeInTheDocument();
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("Tool Surface")).toBeInTheDocument();
    expect(screen.getByText("Workflow Platform")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Planner icon/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Tool Surface icon/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Workflow Platform icon/i })).toBeInTheDocument();
  });

  it("renders contribution focus without relying on lda.chat as category label", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "substrate")!} />);

    const opening = screen.getByRole("region", { name: /thesis opening/i });
    expect(opening).toHaveAttribute("data-opening-focus", "substrate");
    expect(opening).toHaveAttribute("data-support-state", "revealed");
    expect(screen.getByText("Codex / Claude / OpenCode")).toBeInTheDocument();
    expect(screen.getByText("CLI / MCP / APIs")).toBeInTheDocument();
    expect(screen.getByText("submitted substrate")).toBeInTheDocument();
    expect(screen.getByText("Typed · Durable · Inspectable")).toBeInTheDocument();
    expect(screen.queryByText("wf")).not.toBeInTheDocument();
  });
});
