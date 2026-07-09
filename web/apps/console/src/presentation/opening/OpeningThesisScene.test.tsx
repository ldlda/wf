import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { OpeningThesisScene } from "./OpeningThesisScene.js";

const thesisScene = findScene("thesis")!;

afterEach(() => cleanup());

describe("OpeningThesisScene", () => {
  it("renders the title reveal with latent component icons", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "title")!} />);

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

    expect(screen.getByText("Codex / Claude / OpenCode")).toBeInTheDocument();
    expect(screen.getByText("CLI / MCP / APIs")).toBeInTheDocument();
    expect(screen.getByText("submitted substrate")).toBeInTheDocument();
    expect(screen.getByText("Typed · Durable · Inspectable")).toBeInTheDocument();
    expect(screen.queryByText("wf")).not.toBeInTheDocument();
  });
});
