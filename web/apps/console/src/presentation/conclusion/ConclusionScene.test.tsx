import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ConclusionScene } from "./ConclusionScene.js";

const scene = {
  id: "conclusion",
  number: 15,
  title: "Contribution and future work",
  claimClass: "future-work" as const,
  evidencePointer: "Thesis conclusion",
  stageTheme: "night" as const,
  view: "conclusion" as const,
  beats: [],
};

const beat = (id: string) => ({
  id,
  title: id,
  caption: `Caption for ${id}`,
  chatMode: "hidden" as const,
  chatTheme: "dark" as const,
  evidencePresentation: "hidden" as const,
  figure: null,
});

afterEach(() => cleanup());

describe("ConclusionScene", () => {
  it.each(["limits", "future", "conclusion", "questions"])("preserves the labelled contribution boundary for %s", (beatId) => {
    render(<ConclusionScene scene={scene} beat={beat(beatId)} />);
    const map = screen.getByRole("region", { name: "thesis contribution boundary" });
    expect(map).toHaveAttribute("data-conclusion-beat", beatId);
    for (const label of [
      "External planner",
      "Typed workflow substrate",
      "Deterministic runtime",
      "Persisted, inspectable evidence",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("emphasizes all three explicit non-claims in the limits beat", () => {
    render(<ConclusionScene scene={scene} beat={beat("limits")} />);
    const nonClaims = screen.getByRole("list", { name: "explicit non-claims" });
    expect(nonClaims.querySelectorAll("li")).toHaveLength(3);
    expect(nonClaims).toHaveTextContent("Not a production sandbox");
    expect(nonClaims).toHaveTextContent("Not a scheduler");
    expect(nonClaims).toHaveTextContent("Not a broad agent benchmark");
    expect(nonClaims).toHaveAttribute("data-emphasis", "limits");
  });

  it("exposes five labelled future-work icon branches", () => {
    render(<ConclusionScene scene={scene} beat={beat("future")} />);
    const future = screen.getByRole("list", { name: "future work layers" });
    expect(future.querySelectorAll("li")).toHaveLength(5);
    expect(future.querySelectorAll("svg")).toHaveLength(5);
    for (const text of [
      "Agent interface",
      "Security and credentials",
      "Hosted operations",
      "Controlled evaluation",
      "Runtime expansion",
      "Chat or planner loop over wf operations",
      "Secrets, RBAC, sandboxing, policy",
      "Scheduling, daemon lifecycle, monitoring",
      "Frozen prompts, more trials, independent audit",
      "Transactional stores, debugging, providers",
    ]) {
      expect(future).toHaveTextContent(text);
    }
  });

  it("states the closing boundary and recedes future branches", () => {
    render(<ConclusionScene scene={scene} beat={beat("conclusion")} />);
    expect(screen.getByText("Planner proposes; runtime executes.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "future work layers" })).toHaveAttribute("data-state", "receded");
  });
});
