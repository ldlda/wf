import { useCallback, useEffect, useMemo, useState } from "react";
import type { DemoTimelineController } from "../useDemoTimeline.js";
import type { PresentationTargetHealth } from "../../presentation/presentation-target-status.js";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  type AgentMessage,
} from "./events.js";
import type { AgentToolName } from "./tools.js";

export type TimelineAgentMode = "live" | "replay";

export type TimelineAgentOptions = {
  readonly mode: TimelineAgentMode;
  readonly status: PresentationTargetHealth;
};

export type TimelineAgentController = {
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly canRun: boolean;
  readonly runLabel: string;
  readonly runPreparedWorkflow: () => Promise<void>;
  readonly submitSelectedIssues: () => Promise<void>;
  readonly requestRevision: () => Promise<void>;
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

const introMessage = (text: string): AgentMessage =>
  agentTextMessage(
    "timeline-agent-intro",
    "assistant",
    text,
  );

const introForStatus = (status: PresentationTargetHealth): string => {
  switch (status.kind) {
    case "ready":
      return "Live target is ready. Direct slides still show replay evidence until I start the live run.";
    case "active":
      return "Live run is active. Operations are being sent to the workflow server.";
    case "failed":
      return "Replay fallback is active because the live target is unavailable.";
    case "replay":
      return "Replay evidence is active. I can walk through the reviewed recording.";
    case "checking":
      return "Live target configured, checking reachability.";
  }
};

export const useTimelineAgent = (
  demo: DemoTimelineController,
  options: TimelineAgentOptions,
): TimelineAgentController => {
  const modeLabel: TimelineAgentMode =
    options.status.kind === "ready" || options.status.kind === "active"
      ? options.mode
      : "replay";
  const introText = introForStatus(options.status);

  const [messages, setMessages] = useState<ReadonlyArray<AgentMessage>>([
    introMessage(introText),
  ]);

  useEffect(() => {
    setMessages((current) => current.map((message) =>
      message.id === "timeline-agent-intro" ? introMessage(introText) : message,
    ));
  }, [introText]);

  const runLabel = modeLabel === "live" ? "Run prepared workflow" : "Run replay walkthrough";
  const canRun = demo.canStart && !demo.inFlight && demo.state.phase !== "running";

  const runPreparedWorkflow = useCallback(async () => {
    if (!demo.canStart || demo.inFlight || demo.state.phase === "running") return;
    demo.start(modeLabel);
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-start",
      "startRun",
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

  const requestRevision = useCallback(async () => {
    await demo.requestRevision("Request revisions before creating issues.");
    if (modeLabel === "live") await demo.next();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-revision",
      "resumeIssueReview",
      { approved: false, outcome: "cancelled" },
      { outcome: "cancelled", label: "revision requested" },
    ));
  }, [demo]);

  return {
    messages,
    canRun,
    runLabel,
    runPreparedWorkflow,
    submitSelectedIssues,
    requestRevision,
  };
};
