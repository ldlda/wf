import { describe, expect, it } from "vitest";
import {
  authoringPhaseForBeat,
  authoringToolGroupId,
  projectPreparedAuthoring,
  projectPreparedAuthoringThread,
  type AuthoringPhaseId,
} from "./authoring-recording.js";

describe("authoringPhaseForBeat", () => {
  it("returns all five phases in order", () => {
    const phases: readonly AuthoringPhaseId[] = [
      "discover",
      "draft",
      "validate",
      "artifact",
      "deployment",
    ];
    for (const phase of phases) {
      expect(authoringPhaseForBeat(phase)).toBe(phase);
    }
  });

  it("maps beat IDs to expected phases", () => {
    expect(authoringPhaseForBeat("discover")).toBe("discover");
    expect(authoringPhaseForBeat("draft")).toBe("draft");
    expect(authoringPhaseForBeat("validate")).toBe("validate");
    expect(authoringPhaseForBeat("artifact")).toBe("artifact");
    expect(authoringPhaseForBeat("deployment")).toBe("deployment");
  });

  it("throws for unknown beat IDs", () => {
    expect(() => authoringPhaseForBeat("unknown" as AuthoringPhaseId)).toThrow("unknown phase");
  });
});

describe("projectPreparedAuthoring", () => {
  it("returns all five phases in order", () => {
    const phases = projectPreparedAuthoring();
    expect(phases.map((p) => p.phase)).toEqual([
      "discover",
      "draft",
      "validate",
      "artifact",
      "deployment",
    ]);
  });

  it("includes at least one user turn in the recording", () => {
    const phases = projectPreparedAuthoring();
    const allMessages = phases.flatMap((p) => p.conversation);
    const userTurns = allMessages.filter((m) => m.role === "user");
    expect(userTurns.length).toBeGreaterThanOrEqual(1);
  });

  it("includes at least two assistant turns total", () => {
    const phases = projectPreparedAuthoring();
    const allMessages = phases.flatMap((p) => p.conversation);
    const assistantTurns = allMessages.filter((m) => m.role === "assistant");
    expect(assistantTurns.length).toBeGreaterThanOrEqual(2);
  });

  it("has at least two commands per phase", () => {
    const phases = projectPreparedAuthoring();
    for (const phase of phases) {
      expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("labels each prepared command with its actual operation name", () => {
    const titles = projectPreparedAuthoring()
      .flatMap((phase) => phase.commands)
      .map((command) => command.title);

    expect(titles).toEqual([
      "workflow.sources.list",
      "workflow.capabilities.list",
      "workflow.capabilities.inspect",
      "wf schema",
      "workflow.draft_workspaces.create_from_capability",
      "workflow.draft_workspaces.add_step_from_capability",
      "workflow.draft_workspaces.get",
      "workflow.draft_workspaces.validate",
      "workflow.draft_workspaces.set_step_output_map",
      "workflow.draft_workspaces.compile",
      "workflow.draft_workspaces.create_artifact",
      "workflow.artifacts.inspect",
      "workflow.deployments.save",
      "workflow.deployments.validate",
    ]);
  });

  it("starts every command with wf or uv run wf", () => {
    const phases = projectPreparedAuthoring();
    for (const phase of phases) {
      for (const cmd of phase.commands) {
        expect(cmd.command).toMatch(/^(uv run )?wf(\s|$)/);
      }
    }
  });

  it("uses the public CLI command families for each authoring phase", () => {
    const commands = projectPreparedAuthoring()
      .flatMap((phase) => phase.commands)
      .map((command) => command.command);

    expect(commands.some((command) => command === "wf source list")).toBe(true);
    expect(commands.some((command) => command === "wf cap list --source local.lda_report --format ids")).toBe(true);
    expect(commands.some((command) => command === "wf cap inspect local.lda_report.analyze_documents")).toBe(true);
    expect(commands.some((command) => command === "wf schema")).toBe(true);
    expect(commands.some((command) => command.startsWith("wf draft add-step lda_report_workflow"))).toBe(true);
    expect(commands.some((command) => command === "wf draft validate lda_report_workflow")).toBe(true);
    expect(commands.some((command) => command === "wf draft compile lda_report_workflow")).toBe(true);
    expect(commands.some((command) => command === "wf artifact inspect lda_report_case_study --version 1")).toBe(true);
    expect(commands.some((command) => command.startsWith("wf deploy save lda_report_case_study.default"))).toBe(true);
    expect(commands.some((command) => command === "wf deploy validate lda_report_case_study.default")).toBe(true);
  });

  it("has unique beat IDs for each phase", () => {
    const phases = projectPreparedAuthoring();
    const ids = phases.map((p) => p.beatId);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("projectPreparedAuthoringThread", () => {
  it("keeps stable message ids while revealing later phases", () => {
    const draft = projectPreparedAuthoringThread("draft");
    const deployment = projectPreparedAuthoringThread("deployment");

    expect(draft.map(({ id }) => id)).toEqual(
      deployment.slice(0, draft.length).map(({ id }) => id),
    );
  });

  it("projects literal commands as paired workflow tool calls and results", () => {
    const messages = projectPreparedAuthoringThread("discover");
    const parts = messages.flatMap(({ parts }) => parts);
    const calls = parts.filter((part) => part.type === "tool-call");
    const results = parts.filter((part) => part.type === "tool-result");

    expect(calls).toHaveLength(projectPreparedAuthoring()[0]!.commands.length);
    expect(results).toHaveLength(calls.length);
    expect(calls.map((part) => part.call.name)).toEqual([
      "workflow.sources.list",
      "workflow.capabilities.list",
      "workflow.capabilities.inspect",
      "wf schema",
    ]);
  });

  it("uses a stable phase tool-group id", () => {
    expect(authoringToolGroupId("validate")).toBe("authoring-validate");
  });

  it("keeps the canonical projection unchanged without a request override", () => {
    const firstUser = projectPreparedAuthoringThread("discover")
      .find((message) => message.role === "user");
    expect(firstUser?.parts).toEqual([
      {
        type: "text",
        text: "We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?",
      },
    ]);
  });

  it("overrides only the first user request and preserves Discover tool data", () => {
    const canonical = projectPreparedAuthoringThread("discover");
    const overridden = projectPreparedAuthoringThread("discover", "A custom request");
    const canonicalUser = canonical.find((message) => message.role === "user");
    const overriddenUser = overridden.find((message) => message.role === "user");
    const canonicalTools = canonical.find((message) => message.id === "authoring-discover-tools");
    const overriddenTools = overridden.find((message) => message.id === "authoring-discover-tools");

    expect(canonicalUser?.parts).not.toEqual(overriddenUser?.parts);
    expect(overriddenUser?.parts).toEqual([
      { type: "text", text: "A custom request" },
    ]);
    expect(overriddenTools).toEqual(canonicalTools);
  });

  it("projects staged overrides onto their phase user turns", () => {
    const messages = projectPreparedAuthoringThread("validate", undefined, {
      validate: "Edited validation request",
    });
    const validateUser = messages.find(
      (message) => message.id === "authoring-validate-message-0",
    );

    expect(validateUser?.parts).toEqual([{ type: "text", text: "Edited validation request" }]);
  });

  it("projects both staged overrides without changing tool messages", () => {
    const canonical = projectPreparedAuthoringThread("deployment");
    const overridden = projectPreparedAuthoringThread("deployment", undefined, {
      validate: "Edited validation request",
      deployment: "Edited deployment request",
    });

    expect(overridden.find((message) => message.id === "authoring-validate-message-0")?.parts)
      .toEqual([{ type: "text", text: "Edited validation request" }]);
    expect(overridden.find((message) => message.id === "authoring-deployment-message-0")?.parts)
      .toEqual([{ type: "text", text: "Edited deployment request" }]);
    expect(overridden.filter((message) => message.id.endsWith("-tools"))).toEqual(
      canonical.filter((message) => message.id.endsWith("-tools")),
    );
  });

  it("keeps each staged override scoped to its phase", () => {
    const messages = projectPreparedAuthoringThread("deployment", undefined, {
      validate: "Edited validation request",
      deployment: "Edited deployment request",
    });
    const userText = messages
      .filter((message) => message.role === "user")
      .map((message) => message.parts[0]?.type === "text" ? message.parts[0].text : "");

    expect(userText).toEqual([
      "We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?",
      "Edited validation request",
      "Edited deployment request",
    ]);
  });
});
