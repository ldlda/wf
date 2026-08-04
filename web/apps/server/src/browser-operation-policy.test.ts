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
    expect(isBrowserAllowedOperationName("workflow.admin.auth.list")).toBe(false);
  });
});
