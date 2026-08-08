import { describe, expect, it } from "vitest";
import {
  browserAllowedOperationNames,
  isBrowserAllowedOperationName,
} from "./browser-operation-policy.js";

describe("browser operation policy", () => {
  it("pins the authored console boundary independently from generated inventory", () => {
    expect(browserAllowedOperationNames).toEqual([
      "workflow.health",
      "workflow.sources.list",
      "workflow.capabilities.list",
      "workflow.capabilities.inspect",
      "workflow.draft_workspaces.list",
      "workflow.draft_workspaces.get",
      "workflow.draft_workspaces.create_empty",
      "workflow.draft_workspaces.create_from_capability",
      "workflow.draft_workspaces.add_step_from_capability",
      "workflow.draft_workspaces.update_capability_step",
      "workflow.draft_workspaces.set_route",
      "workflow.draft_workspaces.validate",
      "workflow.artifacts.list",
      "workflow.artifacts.inspect",
      "workflow.deployments.list",
      "workflow.deployments.inspect",
      "workflow.deployments.validate",
      "workflow.runs.list",
      "workflow.runs.inspect",
      "workflow.runs.start",
      "workflow.runs.resume",
      "workflow.runs.trace",
    ]);
    expect(isBrowserAllowedOperationName("workflow.health")).toBe(true);
    expect(browserAllowedOperationNames).toContain(
      "workflow.draft_workspaces.add_step_from_capability",
    );
    expect(browserAllowedOperationNames).not.toContain(
      "workflow.draft_workspaces.replace_document",
    );
    expect(isBrowserAllowedOperationName("workflow.admin.auth.list")).toBe(false);
  });
});
