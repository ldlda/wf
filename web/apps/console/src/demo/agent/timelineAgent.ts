import { useCallback, useMemo, useState } from "react";
import type { DemoTimelineController } from "../useDemoTimeline.js";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  type AgentMessage,
} from "./events.js";
import type { AgentToolName } from "./tools.js";

export type TimelineAgentMode = "live" | "replay";

export type TimelineAgentController = {
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly canRun: boolean;
  readonly runLabel: string;
  readonly runPreparedWorkflow: () => Promise<void>;
  readonly submitSelectedIssues: () => Promise<void>;
  readonly cancelReview: () => Promise<void>;
};

const DEFAULT_COMMENT = "Create the selected issue.";

const appendToolMessage = (
  messages: ReadonlyArray<AgentMessage>,
  id: string,
  name: AgentToolName,
  input: unknown,
  output: unknown,
): ReadonlyArray<AgentMessage> => [
  ...messages,
  {
    id,
    role: "assistant",
    parts: [
      agentToolCallPart(`${id}-call`, name, input),
      agentToolResultPart(`${id}-call`, name, "success", output),
    ],
  },
];

export const useTimelineAgent = (
  demo: DemoTimelineController,
  modeLabel: TimelineAgentMode,
): TimelineAgentController => {
  const [messages, setMessages] = useState<ReadonlyArray<AgentMessage>>([
    agentTextMessage(
      "timeline-agent-intro",
      "assistant",
      modeLabel === "live"
        ? "Live workflow server is available. I can run the prepared workflow now."
        : "Replay fallback is active. I can still walk through the prepared workflow evidence.",
    ),
  ]);

  const runLabel = modeLabel === "live" ? "Run prepared workflow" : "Run replay walkthrough";
  const canRun = demo.canStart && !demo.inFlight && demo.state.phase !== "running";

  const runPreparedWorkflow = useCallback(async () => {
    if (!demo.canStart || demo.inFlight) return;
    demo.restart();
    demo.start();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-start",
      "startPreparedReportRun",
      { mode: modeLabel },
      { phase: "started" },
    ));
  }, [demo, modeLabel]);

  const selectedIssueIds = useMemo(
    () => demo.interruptPayload?.proposed_issues.map((issue) => issue.id) ?? [],
    [demo.interruptPayload],
  );

  const submitSelectedIssues = useCallback(async () => {
    if (selectedIssueIds.length === 0) return;
    await demo.submitSelectedIssues(selectedIssueIds, DEFAULT_COMMENT);
    await demo.next();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-submit",
      "resumeIssueReview",
      { selectedIssueIds },
      { outcome: "submitted" },
    ));
  }, [demo, selectedIssueIds]);

  const cancelReview = useCallback(async () => {
    await demo.cancelReview("Cancelled by operator.");
    await demo.next();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-cancel",
      "resumeIssueReview",
      {},
      { outcome: "cancelled" },
    ));
  }, [demo]);

  return {
    messages,
    canRun,
    runLabel,
    runPreparedWorkflow,
    submitSelectedIssues,
    cancelReview,
  };
};