import { useEffect, useState } from "react";
import { callOperation } from "../connection/api.js";
import type { DemoTimelineState } from "../demo/timeline/reducer.js";
import type { PresentationTargetState } from "./live-target.js";
import {
  presentationTargetHealth,
  type PresentationTargetHealth,
  type TargetProbeState,
} from "./presentation-target-status.js";

const liveActive = (state: DemoTimelineState): boolean =>
  state.mode === "live" && state.phase !== "ready";

export const usePresentationTargetStatus = (
  targetState: PresentationTargetState,
  demoState: DemoTimelineState,
): PresentationTargetHealth => {
  const [probe, setProbe] = useState<TargetProbeState>(
    targetState.mode === "live" ? "checking" : "none",
  );
  const [failureReason, setFailureReason] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    if (targetState.mode !== "live") {
      setProbe("none");
      setFailureReason(targetState.reason);
      return;
    }

    setProbe("checking");
    setFailureReason(undefined);
    const probeTarget = async () => {
      try {
        const response = await callOperation("workflow.health", targetState.target, {});
        if (cancelled) return;
        if (response.ok) {
          setProbe("ready");
        } else {
          setProbe("failed");
          setFailureReason(response.error.message);
        }
      } catch (error: unknown) {
        if (cancelled) return;
        setProbe("failed");
        setFailureReason(error instanceof Error ? error.message : String(error));
      }
    };
    void probeTarget();
    return () => {
      cancelled = true;
    };
  }, [targetState]);

  return presentationTargetHealth({
    target: targetState.mode === "live" ? targetState.target : null,
    probe,
    liveActive: liveActive(demoState),
    failureReason,
  });
};