import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { findBeat, findScene } from "../storyboard.js";
import { PreparedAuthoringLifecycleScene } from "./PreparedAuthoringLifecycleScene.js";

afterEach(() => cleanup());

const renderBeat = (beatId: string, onAdvance?: () => void, discussionRail?: ReactNode) => {
  const scene = findScene("prepared-lifecycle");
  const beat = findBeat("prepared-lifecycle", beatId);
  if (!scene || !beat) throw new Error(`missing prepared-lifecycle/${beatId}`);
  return render(
    <PreparedAuthoringLifecycleScene
      scene={scene}
      beat={beat}
      onAdvance={onAdvance}
      discussionRail={discussionRail}
    />,
  );
};

describe("PreparedAuthoringLifecycleScene", () => {
  it("discover shows sources, capabilities, and schema", () => {
    renderBeat("discover");
    expect(screen.getByRole("region", { name: "prepared workflow authoring lifecycle" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    expect(within(screen.getByRole("list", { name: /prepared authoring lifecycle/i })).getByText("Discover"))
      .toBeInTheDocument();
    expect(screen.getAllByText(/sources|capabilities|schema/i).length).toBeGreaterThanOrEqual(1);
  });

  it("draft shows graph or routes", () => {
    renderBeat("draft");
    expect(within(screen.getByRole("list", { name: /prepared authoring lifecycle/i })).getByText("Author"))
      .toBeInTheDocument();
    expect(screen.getAllByText(/graph|routes/i).length).toBeGreaterThanOrEqual(1);
  });

  it("diagnose shows the structured validation operation in its frame", () => {
    renderBeat("diagnose");
    expect(screen.getByRole("region", { name: "prepared workflow authoring lifecycle" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    const frame = screen.getByRole("region", { name: /active authoring operation/i });
    expect(frame).toHaveTextContent("workflow.draft_workspaces.validate");
    expect(frame).toHaveTextContent("wf draft validate lda_report_workflow");
    expect(frame).toHaveTextContent("missing_outcome_edge");
    expect(frame).toHaveTextContent("nodes[analyze]");
    expect(frame).toHaveTextContent(/missing edges for outcomes.*ok/i);
    const setup = within(frame).getByRole("note", { name: /prepared fault injection/i });
    expect(setup).toHaveTextContent(/valid revision 2/i);
    expect(setup).toHaveTextContent(/remove analyze\.ok/i);
    expect(setup).toHaveTextContent(/invalid revision 3/i);
    expect(within(screen.getByRole("region", { name: "draft validation diagnostic" }))
      .queryByRole("note", { name: /prepared fault injection/i })).not.toBeInTheDocument();
    expect(frame).toHaveAttribute("data-authoring-step", "diagnose");
    expect(frame).toHaveAttribute("data-recording-phase", "validate");
    expect(screen.getByRole("region", { name: "draft validation diagnostic" })).toHaveAttribute(
      "data-authoring-result",
      "diagnostic",
    );
  });

  it("repair shows the route repair operation and valid result", () => {
    const scene = findScene("prepared-lifecycle");
    const repairBeat = findBeat("prepared-lifecycle", "repair");
    if (!scene || !repairBeat) throw new Error("missing prepared-lifecycle/repair");

    const { rerender } = renderBeat("diagnose");
    rerender(<PreparedAuthoringLifecycleScene scene={scene} beat={repairBeat} />);
    const frame = screen.getByRole("region", { name: /active authoring operation/i });
    expect(frame).toHaveTextContent("workflow.draft_workspaces.set_route");
    expect(frame).toHaveTextContent(/wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__/i);
    expect(frame).toHaveTextContent("Valid");
    expect(frame).toHaveTextContent("Revision 4");
    expect(frame).toHaveTextContent("0 diagnostics");
    expect(frame).toHaveTextContent(/prepared workflow lifecycle/i);
    expect(frame).toHaveAttribute("data-authoring-step", "repair");
    expect(frame).toHaveAttribute("data-recording-phase", "validate");
    const rail = screen.getByRole("list", { name: /prepared authoring lifecycle/i });
    expect(within(rail).getByText("Focused route edit")).toBeInTheDocument();
    expect(within(rail).queryByText(/output-map/i)).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "route repair result" })).toHaveAttribute(
      "data-authoring-result",
      "repair",
    );
  });

  it("artifact shows immutable ID and version", () => {
    renderBeat("artifact");
    expect(within(screen.getByRole("list", { name: /prepared authoring lifecycle/i })).getByText("Artifact"))
      .toBeInTheDocument();
    expect(screen.getAllByText(/lda_report_case_study/i).length).toBeGreaterThanOrEqual(1);
  });

  it("deployment shows bindings and validation", () => {
    renderBeat("deployment");
    expect(screen.getAllByText("Deployment").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/lda_report_case_study\.default/i).length).toBeGreaterThanOrEqual(1);
  });

  it.each([
    ["discover", "source inventory result"],
    ["draft", "draft structure result"],
    ["diagnose", "draft validation diagnostic"],
    ["repair", "route repair result"],
    ["artifact", "immutable artifact result"],
    ["deployment", "runnable deployment result"],
  ] as const)("renders %s as the primary phase visual", (beatId, label) => {
    renderBeat(beatId);
    expect(screen.getByRole("region", { name: label })).toBeInTheDocument();
  });

  it("keeps the assistant and dominant phase visual visible as stable siblings", () => {
    renderBeat("draft");

    const workspace = screen.getByRole("region", { name: "prepared workflow authoring lifecycle" });
    const assistant = screen.getByRole("complementary", { name: /prepared authoring assistant/i });
    const frame = screen.getByRole("region", { name: "active authoring operation" });
    const visual = screen.getByRole("region", { name: "draft structure result" });

    expect(workspace).toContainElement(assistant);
    expect(workspace).toContainElement(frame);
    expect(workspace).toContainElement(visual);
    expect(assistant).toHaveAttribute("data-phase", "draft");
    expect(assistant).toHaveAttribute("data-surface", "prepared-replay");
    expect(assistant).toHaveAttribute("data-visual-role", "support");
    expect(assistant.querySelector('[data-surface="stage"]')).toBeInTheDocument();
    expect(workspace.querySelector(".prepared-lifecycle-scene__dock")).not.toBeInTheDocument();
    expect(workspace.querySelector("[role='dialog']")).not.toBeInTheDocument();
    expect(workspace.querySelector("[aria-label='prepared authoring lifecycle']"))
      .toBeInTheDocument();
    expect(visual).toHaveAttribute("data-presentation-surface", "editorial");
    expect(visual).toHaveAttribute("data-visual-role", "primary");
    expect(workspace.querySelector('[data-visual-role="lifecycle-primary"]')).toBe(visual.parentElement);
    expect(workspace.querySelectorAll('[data-visual-role="lifecycle-primary"]')).toHaveLength(1);
  });

  it("projects a custom discover submission into the prepared conversation", async () => {
    const user = userEvent.setup();
    renderBeat("discover");

    const input = screen.getByRole("textbox", { name: /message to authoring assistant/i });
    await user.type(input, "Inspect the report source first.");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    const conversation = screen.getByRole("log", { name: "prepared authoring conversation" });
    expect(within(conversation).getByText("Inspect the report source first.")).toBeInTheDocument();
  });

  it.each([
    ["draft", true],
    ["artifact", true],
    ["diagnose", false],
    ["repair", false],
    ["deployment", false],
  ] as const)("%s submission advances only when its beat owns the transition", async (beatId, advances) => {
    const user = userEvent.setup();
    const onAdvance = vi.fn();
    renderBeat(beatId, onAdvance);

    const input = screen.getByRole("textbox", { name: /message to authoring assistant/i });
    if (beatId === "diagnose" || beatId === "repair") {
      await user.type(input, "Review the validation result.");
    }
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(onAdvance).toHaveBeenCalledTimes(advances ? 1 : 0);
  });

  it.each([
    ["discover", "Discover"],
    ["draft", "Draft"],
    ["diagnose", "Diagnose"],
    ["repair", "Repair"],
    ["artifact", "Artifact"],
    ["deployment", "Deployment"],
  ] as const)("marks %s as the active lifecycle evidence beat", (beatId, label) => {
    renderBeat(beatId);
    const evidence = screen.getByRole("region", { name: /active authoring operation/i });
    const workspace = screen.getByRole("region", { name: "prepared workflow authoring lifecycle" });

    expect(evidence).toHaveAttribute("data-visual-role", "lifecycle-primary");
    expect(workspace.querySelectorAll('[data-visual-role="lifecycle-primary"]')).toHaveLength(1);
    expect(screen.getByRole("list", { name: /prepared authoring lifecycle/i }).querySelector('[data-active="true"]'))
      .toHaveTextContent(label);
  });

  it("synchronizes the assistant phase, active group, rail, and visual", () => {
    renderBeat("diagnose");

    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i }))
      .toHaveAttribute("data-phase", "diagnose");
    expect(screen.getByRole("button", { name: /validate.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /draft.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("list", { name: /prepared authoring lifecycle/i })
      .querySelector("[data-active='true']"))
      .toHaveTextContent("Diagnose");
    const chat = screen.getByRole("log", { name: "prepared authoring conversation" });
    expect(chat).toHaveAttribute("data-surface", "stage");
    expect(screen.getByRole("region", { name: "draft validation diagnostic" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
  });

  it("does not render the obsolete trace modal or receipt", () => {
    renderBeat("diagnose");
    expect(screen.queryByRole("button", { name: "Agent trace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Authoring trace" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("prepared authoring receipt")).not.toBeInTheDocument();
  });

  it("renders the six-step prepared authoring lifecycle rail", () => {
    renderBeat("artifact");
    const rail = screen.getByRole("list", { name: /prepared authoring lifecycle/i });
    expect(rail).toBeInTheDocument();
    expect(within(rail).getAllByRole("listitem")).toHaveLength(6);
    expect(within(rail).getByText("Diagnose")).toBeInTheDocument();
    expect(within(rail).getByText("Repair")).toBeInTheDocument();
    expect(within(rail).getByText("Sources, capabilities, schemas")).toBeInTheDocument();
  });

  it("places defense questions in a presentation-only grid row", () => {
    renderBeat(
      "diagnose",
      undefined,
      <aside aria-label="defense discussion topics">Defense questions</aside>,
    );

    const workspace = screen.getByRole("region", { name: "prepared workflow authoring lifecycle" });
    const discussion = workspace.querySelector(".prepared-lifecycle-scene__discussion");

    expect(discussion?.tagName).toBe("SECTION");
    expect(discussion).toHaveAttribute("data-discussion-placement", "presentation-column");
    expect(discussion?.parentElement).toBe(workspace);
    expect(discussion).toContainElement(screen.getByLabelText("defense discussion topics"));
    expect(workspace.querySelector(".presentation-assistant-pane")?.parentElement).toBe(workspace);
  });

  it("highlights the active phase in the rail", () => {
    renderBeat("deployment");
    const rail = screen.getByRole("list", { name: /prepared authoring lifecycle/i });
    const active = rail.querySelector("[data-active='true']");
    expect(active).toBeInTheDocument();
    expect(active).toHaveTextContent("Deployment");
  });

  it("falls back to discovery for an unexpected storyboard beat", () => {
    const scene = findScene("prepared-lifecycle")!;
    const knownBeat = findBeat("prepared-lifecycle", "discover")!;
    const unexpectedBeat = { ...knownBeat, id: "unexpected" };

    render(<PreparedAuthoringLifecycleScene scene={scene} beat={unexpectedBeat} />);

    expect(screen.getByRole("region", { name: "source inventory result" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /prepared authoring lifecycle/i }).querySelector("[data-active='true']"))
      .toHaveTextContent("Discover");
  });
});
