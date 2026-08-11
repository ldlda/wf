import { useCallback, useEffect, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  callCapability,
  type CapabilityCallRequest,
} from "../domain/capability-call-client.js";
import type { CapabilityCallResult } from "../domain/capability-models.js";
import type { ConsoleWriteExecutor } from "../domain/write-executor.js";

export type CapabilityPlaygroundPhase =
  | "disconnected"
  | "idle"
  | "calling"
  | "result"
  | "error";

export type CapabilityPlaygroundController = {
  readonly phase: CapabilityPlaygroundPhase;
  readonly result: CapabilityCallResult | null;
  readonly message: string | null;
  readonly acknowledged: boolean;
  readonly deploymentId: string;
  readonly setAcknowledged: (value: boolean) => void;
  readonly setDeploymentId: (value: string) => void;
  readonly call: (payload: Record<string, unknown>) => void;
  readonly reset: () => void;
};

type PlaygroundState = Omit<
  CapabilityPlaygroundController,
  "setAcknowledged" | "setDeploymentId" | "call" | "reset"
>;

type SelectionIdentity = {
  readonly writeExecutor: ConsoleWriteExecutor | null;
  readonly connectedTarget: string | null;
  readonly qualifiedName: string | null;
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const isSameSelection = (
  left: SelectionIdentity | null,
  right: SelectionIdentity,
): boolean =>
  left !== null &&
  left.writeExecutor === right.writeExecutor &&
  left.connectedTarget === right.connectedTarget &&
  left.qualifiedName === right.qualifiedName;

export const useCapabilityPlayground = (
  qualifiedName: string | null,
): CapabilityPlaygroundController => {
  const { connectedTarget, writeExecutor } = useConsoleWorkspace();
  const isConnected = writeExecutor !== null && connectedTarget !== null;
  const selection: SelectionIdentity = {
    writeExecutor,
    connectedTarget,
    qualifiedName,
  };
  const selectionRef = useRef<SelectionIdentity>(selection);
  const committedSelectionRef = useRef<SelectionIdentity | null>(null);
  const generationRef = useRef(0);
  const pendingRef = useRef(false);
  const deploymentIdRef = useRef("");
  const [state, setState] = useState<PlaygroundState>(() => ({
    phase: isConnected ? "idle" : "disconnected",
    result: null,
    message: null,
    acknowledged: false,
    deploymentId: "",
  }));

  if (!isSameSelection(selectionRef.current, selection)) {
    // Invalidate an in-flight call during render so a promise resolving before
    // the reset effect cannot publish data for the previous selection.
    selectionRef.current = selection;
    generationRef.current += 1;
    pendingRef.current = false;
  }

  const resetState = useCallback((): void => {
    deploymentIdRef.current = "";
    setState({
      phase: isConnected ? "idle" : "disconnected",
      result: null,
      message: null,
      acknowledged: false,
      deploymentId: "",
    });
  }, [isConnected]);

  useEffect(() => {
    committedSelectionRef.current = selectionRef.current;
    resetState();
  }, [connectedTarget, qualifiedName, resetState, writeExecutor]);

  const setAcknowledged = useCallback((value: boolean): void => {
    setState((current) => ({ ...current, acknowledged: value }));
  }, []);

  const setDeploymentId = useCallback((value: string): void => {
    deploymentIdRef.current = value;
    setState((current) => ({ ...current, deploymentId: value }));
  }, []);

  const reset = useCallback((): void => {
    generationRef.current += 1;
    pendingRef.current = false;
    resetState();
  }, [resetState]);

  const call = useCallback(
    (payload: Record<string, unknown>): void => {
      if (
        writeExecutor === null ||
        connectedTarget === null ||
        qualifiedName === null ||
        !qualifiedName.trim() ||
        pendingRef.current ||
        !isSameSelection(committedSelectionRef.current, selectionRef.current)
      ) return;

      const generation = ++generationRef.current;
      const requestSelection = selectionRef.current;
      pendingRef.current = true;
      setState((current) => ({
        ...current,
        phase: "calling",
        result: null,
        message: null,
      }));

      const request: CapabilityCallRequest = {
        qualifiedName,
        payload,
        deploymentId: deploymentIdRef.current,
      };
      void callCapability(writeExecutor, request).then(
        (result) => {
          if (
            generation !== generationRef.current ||
            !isSameSelection(committedSelectionRef.current, requestSelection)
          ) return;
          pendingRef.current = false;
          setState((current) => ({
            ...current,
            phase: "result",
            result,
            message: null,
          }));
        },
        (error: unknown) => {
          if (
            generation !== generationRef.current ||
            !isSameSelection(committedSelectionRef.current, requestSelection)
          ) return;
          pendingRef.current = false;
          setState((current) => ({
            ...current,
            phase: "error",
            result: null,
            message: errorMessage(error),
          }));
        },
      );
    },
    [connectedTarget, qualifiedName, writeExecutor],
  );

  const hasCurrentSelection = isSameSelection(
    committedSelectionRef.current,
    selection,
  );
  const visibleState: PlaygroundState = hasCurrentSelection
    ? state
    : {
        phase: isConnected ? "idle" : "disconnected",
        result: null,
        message: null,
        acknowledged: false,
        deploymentId: "",
      };

  return {
    ...visibleState,
    setAcknowledged,
    setDeploymentId,
    call,
    reset,
  };
};
