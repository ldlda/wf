import { describe, expect, it } from "vitest";
import { mainScenes } from "./storyboard.js";
import {
  beatVisualContractFor,
  coherenceForScene,
  demoSurfaceForBeat,
  sceneCoherenceMatrix,
} from "./presentation-coherence.js";

describe("presentation coherence matrix", () => {
  it("covers every storyboard scene exactly once", () => {
    const sceneIds = mainScenes.map((scene) => scene.id);
    const matrixIds = sceneCoherenceMatrix.map((entry) => entry.sceneId);

    expect(matrixIds).toEqual(sceneIds);
    expect(new Set(matrixIds).size).toBe(sceneIds.length);
  });

  it("gives every scene one primary artifact and at most one support surface", () => {
    for (const scene of mainScenes) {
      const entry = coherenceForScene(scene.id);

      expect(entry.primaryArtifact.length).toBeGreaterThan(0);
      expect(entry.supportSurface).not.toContain("+");
      expect(entry.chatRole).toMatch(/^(hidden|narration|approval|trace)$/);
    }
  });

  it("keeps baseline scenes 3 through 5 stable", () => {
    expect(coherenceForScene("positioning")).toMatchObject({
      primaryArtifact: "positioning-map",
      supportSurface: "discussion-rail",
      chatRole: "hidden",
    });
    expect(coherenceForScene("planner-runtime")).toMatchObject({
      primaryArtifact: "boundary-diagram",
      supportSurface: "discussion-rail",
      chatRole: "hidden",
    });
    expect(coherenceForScene("lifecycle")).toMatchObject({
      primaryArtifact: "lifecycle-rail",
      supportSurface: "current-state-panel",
      chatRole: "hidden",
    });
  });

  it("classifies demo beats into one primary surface and one support surface", () => {
    expect(demoSurfaceForBeat("run-from-deployment", "graph")).toEqual({
      primarySurface: "workflow-graph",
      supportSurface: "run-receipt",
    });
    expect(demoSurfaceForBeat("typed-human-boundary", "approval")).toEqual({
      primarySurface: "interrupt-approval",
      supportSurface: "facts-only",
    });
    expect(demoSurfaceForBeat("resume-output-evidence", "trace")).toEqual({
      primarySurface: "trace-evidence",
      supportSurface: "output-summary",
    });
  });

  it("defines a focal contract for the opening title", () => {
    expect(beatVisualContractFor("thesis", "title")).toMatchObject({
      mode: "focal",
      primarySurface: "title-boundary",
      supportSurface: "none",
    });
  });

  it("defines semantic zoom for architecture and evidence staging for evaluation", () => {
    expect(beatVisualContractFor("architecture", "runtime")).toMatchObject({
      mode: "zoom",
      primarySurface: "interactive-architecture",
    });
    expect(beatVisualContractFor("prepared-lifecycle", "discover")).toMatchObject({
      mode: "evidence",
      primarySurface: "prepared-discovery",
    });
    expect(beatVisualContractFor("prepared-lifecycle", "draft")).toMatchObject({
      mode: "evidence",
      primarySurface: "draft-graph",
    });
    expect(beatVisualContractFor("prepared-lifecycle", "diagnose")).toMatchObject({
      mode: "evidence",
      primarySurface: "prepared-diagnostic",
    });
    expect(beatVisualContractFor("prepared-lifecycle", "repair")).toMatchObject({
      mode: "evidence",
      primarySurface: "prepared-repair",
    });
    expect(beatVisualContractFor("prepared-lifecycle", "artifact")).toMatchObject({
      mode: "evidence",
      primarySurface: "artifact",
    });
    expect(beatVisualContractFor("prepared-lifecycle", "deployment")).toMatchObject({
      mode: "evidence",
      primarySurface: "deployment",
    });
    expect(beatVisualContractFor("evaluation", "validity")).toMatchObject({
      mode: "evidence",
      primarySurface: "evaluation-validity",
      supportSurface: "audit-reconciliation",
    });
  });

  it("fails closed for an unknown scene beat", () => {
    expect(() => beatVisualContractFor("unknown", "beat")).toThrow(
      "No visual contract for unknown/beat",
    );
  });
});
