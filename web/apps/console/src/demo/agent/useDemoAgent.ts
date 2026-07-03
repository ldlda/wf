import { useCallback, useRef, useState } from "react";
import type { AgentApproval, AgentDriver, AgentMessage, PresentationToolAction } from "./events.js";

export type DemoAgentPhase = "idle" | "running" | "awaiting-approval" | "completed" | "failed";

export type DemoAgentController = {
  readonly phase: DemoAgentPhase;
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly pendingActions: ReadonlyArray<PresentationToolAction>;
  readonly startPreparedReplay: () => void;
  readonly submitApproval: (decision: AgentApproval) => void;
  readonly clearPendingActions: () => void;
  readonly reset: () => void;
};

const collectActions = (message: AgentMessage): ReadonlyArray<PresentationToolAction> =>
  message.parts.flatMap((part) => part.type === "presentation-action" ? [part.action] : []);

export const useDemoAgent = (driver: AgentDriver): DemoAgentController => {
  const [phase, setPhase] = useState<DemoAgentPhase>("idle");
  const [messages, setMessages] = useState<ReadonlyArray<AgentMessage>>([]);
  const [pendingActions, setPendingActions] = useState<ReadonlyArray<PresentationToolAction>>([]);
  const abortRef = useRef<AbortController | null>(null);
  const approvalResolveRef = useRef<((decision: AgentApproval) => void) | null>(null);
  const approvalRejectRef = useRef<((error: Error) => void) | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (approvalRejectRef.current) {
      approvalRejectRef.current(new DOMException("Agent reset while awaiting approval", "AbortError"));
      approvalResolveRef.current = null;
      approvalRejectRef.current = null;
    }
    setPhase("idle");
    setMessages([]);
    setPendingActions([]);
  }, []);

  const clearPendingActions = useCallback(() => {
    setPendingActions([]);
  }, []);

  const submitApproval = useCallback((decision: AgentApproval) => {
    if (approvalResolveRef.current) {
      approvalResolveRef.current(decision);
      approvalResolveRef.current = null;
      approvalRejectRef.current = null;
      setPhase("running");
    }
  }, []);

  const requestApproval = useCallback((signal: AbortSignal): Promise<AgentApproval> => {
    setPhase("awaiting-approval");
    return new Promise<AgentApproval>((resolve, reject) => {
      approvalResolveRef.current = resolve;
      approvalRejectRef.current = reject;

      if (signal.aborted) {
        reject(new DOMException("Agent aborted while awaiting approval", "AbortError"));
        approvalResolveRef.current = null;
        approvalRejectRef.current = null;
        return;
      }

      const onAbort = () => {
        signal.removeEventListener("abort", onAbort);
        reject(new DOMException("Agent aborted while awaiting approval", "AbortError"));
        approvalResolveRef.current = null;
        approvalRejectRef.current = null;
      };
      signal.addEventListener("abort", onAbort);
    });
  }, []);

  const startPreparedReplay = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setPhase("running");
    setMessages([]);
    setPendingActions([]);

    const drive = async () => {
      try {
        for await (const message of driver.run({ target: null }, controller.signal, (signal) => requestApproval(signal))) {
          if (controller.signal.aborted) break;
          setMessages((current) => [...current, message]);
          const actions = collectActions(message);
          if (actions.length > 0) {
            setPendingActions((current) => [...current, ...actions]);
          }
        }
        if (!controller.signal.aborted) {
          setPhase("completed");
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          const msg = error instanceof Error ? error.message : String(error);
          setMessages((current) => [
            ...current,
            { id: "agent-failure", role: "assistant", parts: [{ type: "error", message: msg }] },
          ]);
          setPhase("failed");
        }
      }
    };
    void drive();
  }, [driver, requestApproval]);

  return {
    phase,
    messages,
    pendingActions,
    startPreparedReplay,
    submitApproval,
    clearPendingActions,
    reset,
  };
};
