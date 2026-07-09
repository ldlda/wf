import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  Conversation,
  ConversationContent,
  Message,
  MessageContent,
  MessageResponse,
  PromptAction,
  Tool,
  ToolInput,
  ToolOutput,
} from "./ChatPrimitives.js";

describe("ChatPrimitives", () => {
  it("renders conversation and message landmarks", () => {
    render(
      <Conversation mode="dock">
        <ConversationContent>
          <Message from="assistant">
            <MessageContent>
              <MessageResponse>Live target is ready.</MessageResponse>
            </MessageContent>
          </Message>
        </ConversationContent>
      </Conversation>,
    );

    expect(screen.getByRole("log", { name: "operator conversation" })).toHaveAttribute("data-mode", "dock");
    expect(screen.getByText("Live target is ready.")).toBeInTheDocument();
  });

  it("keeps tool details collapsed by default and expands on click", async () => {
    const user = userEvent.setup();
    render(
      <Tool label="Workflow operation" name="workflow.runs.start" state="success">
        <ToolInput input={{ deployment_id: "demo.default" }} />
        <ToolOutput status="success" output={{ run_id: "run_123" }} />
      </Tool>,
    );

    const toggle = screen.getByRole("button", { name: /workflow operation/i });
    expect(screen.queryByText(/deployment_id/)).not.toBeInTheDocument();

    await user.click(toggle);

    expect(screen.getByText(/deployment_id/)).toBeInTheDocument();
    expect(screen.getByText(/run_123/)).toBeInTheDocument();
  });

  it("supports default-open tools for currently relevant operations", () => {
    render(
      <Tool label="Approval required" name="resumeIssueReview" state="pending" defaultOpen>
        <ToolOutput status="pending" output="waiting for operator" />
      </Tool>,
    );

    expect(screen.getByText("waiting for operator")).toBeInTheDocument();
  });

  it("renders prompt action buttons", async () => {
    const user = userEvent.setup();
    const run = vi.fn();
    render(<PromptAction label="Run prepared workflow" onClick={run} disabled={false} />);

    await user.click(screen.getByRole("button", { name: "Run prepared workflow" }));

    expect(run).toHaveBeenCalledOnce();
  });
});
