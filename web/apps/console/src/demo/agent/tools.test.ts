import { describe, expect, it } from "vitest";
import { AGENT_TOOLS, isAllowedAgentToolName } from "./tools.js";

describe("agent tools", () => {
  it("separates workflow tools from presentation tools", () => {
    expect(AGENT_TOOLS.inspectDeployment.kind).toBe("workflow");
    expect(AGENT_TOOLS.startPreparedReportRun.kind).toBe("workflow");
    expect(AGENT_TOOLS.resumeIssueReview.kind).toBe("workflow");
    expect(AGENT_TOOLS.readRunTrace.kind).toBe("workflow");
    expect(AGENT_TOOLS.selectWorkflowNode.kind).toBe("presentation");
    expect(AGENT_TOOLS.openEvidence.kind).toBe("presentation");
  });

  it("rejects unknown tool names", () => {
    expect(isAllowedAgentToolName("selectWorkflowNode")).toBe(true);
    expect(isAllowedAgentToolName("readFile")).toBe(false);
    expect(isAllowedAgentToolName("authorArbitraryWorkflow")).toBe(false);
  });
});
