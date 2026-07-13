import { describe, expect, it } from "vitest";
import { projectPreparedAuthoring } from "./authoring-recording.js";
import {
  projectPreparedAuthoringPhase,
  projectPreparedLifecycleStep,
  recordingPhaseForStep,
} from "./authoring-projection.js";

describe("projectPreparedAuthoringPhase", () => {
  it("projects the discover phase with sources, capabilities, schema", () => {
    const phase = projectPreparedAuthoringPhase("discover");
    expect(phase.label).toBe("Discover");
    expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    expect(phase.summary).toMatch(/sources|capabilities|schema/i);
    expect(phase.visual).toMatchObject({ kind: "inventory" });
  });

  it("projects the draft phase with graph and routes", () => {
    const phase = projectPreparedAuthoringPhase("draft");
    expect(phase.label).toBe("Draft");
    expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    expect(phase.summary).toMatch(/graph|routes/i);
    expect(phase.visual).toMatchObject({ kind: "graph" });
  });

  it("projects the validate phase with diagnosis and repair", () => {
    const phase = projectPreparedAuthoringPhase("validate");
    expect(phase.label).toBe("Validate");
    expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    expect(phase.summary).toMatch(/diagnos|repair/i);
    expect(phase.visual).toMatchObject({ kind: "repair" });
  });

  it("projects the artifact phase with immutable ID and version", () => {
    const phase = projectPreparedAuthoringPhase("artifact");
    expect(phase.label).toBe("Artifact");
    expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    expect(phase.summary).toMatch(/id/i);
    expect(phase.summary).toMatch(/version/i);
    expect(phase.visual).toMatchObject({ kind: "artifact" });
  });

  it("projects the deployment phase with bindings and validation", () => {
    const phase = projectPreparedAuthoringPhase("deployment");
    expect(phase.label).toBe("Deployment");
    expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    expect(phase.summary).toMatch(/bind|validat/i);
    expect(phase.visual).toMatchObject({ kind: "bindings" });
  });

  it("keeps the validation diagnostic and repair command distinct", () => {
    const phase = projectPreparedAuthoringPhase("validate");
    const diagnosticCmd = phase.commands.find(
      (cmd) => cmd.result === "diagnostic" && cmd.detail?.includes("missing_outcome_edge"),
    );
    const repairCmd = phase.commands.find((cmd) => cmd.command.includes("draft set-route"));
    expect(diagnosticCmd).toBeDefined();
    expect(repairCmd).toBeDefined();
    expect(diagnosticCmd).not.toBe(repairCmd);
  });

  it("uses real public command syntax from the recording", () => {
    const recording = projectPreparedAuthoring();
    const allCommands = recording.flatMap((p) => p.commands);
    for (const cmd of allCommands) {
      expect(typeof cmd.command).toBe("string");
      expect(typeof cmd.summary).toBe("string");
      expect(["success", "diagnostic"]).toContain(cmd.result);
    }
  });

  it("splits one recorded validate phase into diagnosis and repair presentation steps", () => {
    const diagnose = projectPreparedLifecycleStep("diagnose");
    const repair = projectPreparedLifecycleStep("repair");

    expect(diagnose.recordingPhase).toBe("validate");
    expect(repair.recordingPhase).toBe("validate");
    expect(diagnose.focus).toBe("diagnose");
    expect(repair.focus).toBe("repair");
    expect(diagnose.primaryCommand.title).toBe("workflow.draft_workspaces.validate");
    expect(diagnose.primaryCommand.detail).toContain("missing_outcome_edge");
    expect(repair.primaryCommand.title).toBe("workflow.draft_workspaces.set_route");
    expect(repair.primaryCommand.command).toContain("--revision 3 --step analyze --outcome ok --to __end__");
    expect(diagnose.evidence.kind).toBe("diagnostic");
    expect(repair.evidence.kind).toBe("repair");
  });

  it("projects six presentation steps from five recorded phases", () => {
    const steps = [
      "discover",
      "draft",
      "diagnose",
      "repair",
      "artifact",
      "deployment",
    ] as const;

    expect(steps.map(recordingPhaseForStep)).toEqual([
      "discover",
      "draft",
      "validate",
      "validate",
      "artifact",
      "deployment",
    ]);
    expect(steps.map((step) => projectPreparedLifecycleStep(step).step)).toEqual(steps);
  });
});
