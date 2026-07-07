import { useCallback, useEffect, useRef, useState } from "react";
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

type PendingApproval = {
  readonly resolve: (decision: AgentApproval) => void;
  readonly reject: (error: Error) => void;
  readonly signal: AbortSignal;
  readonly abortHandler: () => void;
};

export const useDemoAgent = (driver: AgentDriver): DemoAgentController => {
  const [phase, setPhase] = useState<DemoAgentPhase>("idle");
  const [messages, setMessages] = useState<ReadonlyArray<AgentMessage>>([]);
  const [pendingActions, setPendingActions] = useState<ReadonlyArray<PresentationToolAction>>([]);
  const abortRef = useRef<AbortController | null>(null);
  const pendingApprovalRef = useRef<PendingApproval | null>(null);

  const clearPendingApproval = useCallback((pending: PendingApproval | null) => {
    if (pending === null || pendingApprovalRef.current !== pending) return;
    pending.signal.removeEventListener("abort", pending.abortHandler);
    pendingApprovalRef.current = null;
  }, []);

  const abortPendingApproval = useCallback((reason: string) => {
    const pending = pendingApprovalRef.current;
    if (!pending) return;
    clearPendingApproval(pending);
    pending.reject(new DOMException(reason, "AbortError"));
  }, [clearPendingApproval]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    abortPendingApproval("Agent reset while awaiting approval");
    setPhase("idle");
    setMessages([]);
    setPendingActions([]);
  }, [abortPendingApproval]);

  const clearPendingActions = useCallback(() => {
    setPendingActions([]);
  }, []);

  const submitApproval = useCallback((decision: AgentApproval) => {
    const pending = pendingApprovalRef.current;
    if (!pending) return;
    clearPendingApproval(pending);
    pending.resolve(decision);
    setPhase("running");
  }, [clearPendingApproval]);

  const requestApproval = useCallback((signal: AbortSignal): Promise<AgentApproval> => {
    setPhase("awaiting-approval");
    return new Promise<AgentApproval>((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException("Agent aborted while awaiting approval", "AbortError"));
        return;
      }

      const onAbort = () => {
        const pending = pendingApprovalRef.current;
        if (!pending || pending.abortHandler !== onAbort) return;
        clearPendingApproval(pending);
        reject(new DOMException("Agent aborted while awaiting approval", "AbortError"));
      };
      const pending: PendingApproval = {
        resolve,
        reject,
        signal,
        abortHandler: onAbort,
      };
      pendingApprovalRef.current = pending;
      signal.addEventListener("abort", onAbort);
    });
  }, [clearPendingApproval]);

  useEffect(() => () => {
    abortRef.current?.abort();
    abortRef.current = null;
    abortPendingApproval("Agent unmounted while awaiting approval");
  }, [abortPendingApproval]);

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
