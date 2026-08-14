import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createAuthoringContractClient,
  type AuthoringContractClient,
} from "../domain/authoring-contract-client.js";
import type { AuthoringContractInventory } from "../domain/authoring-contract-models.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";

export type AuthoringContractPhase =
  | "disconnected"
  | "idle"
  | "loading"
  | "ready"
  | "error";

export type UseAuthoringContractOptions = {
  readonly workspaceId: string | null;
  readonly revision: number | null;
  readonly selectedStepId?: string | null;
};

export type AuthoringContractController = {
  readonly phase: AuthoringContractPhase;
  readonly inventory: AuthoringContractInventory | null;
  readonly message: string | null;
  readonly refresh: () => void;
};

type RequestIdentity = {
  readonly readExecutor: ConsoleReadExecutor;
  readonly connectedTarget: string;
  readonly workspaceId: string;
  readonly revision: number;
  readonly selectedStepId: string | null;
};

type StoredInventory = {
  readonly request: RequestIdentity;
  readonly inventory: AuthoringContractInventory;
};

type AuthoringContractState = {
  readonly phase: AuthoringContractPhase;
  readonly stored: StoredInventory | null;
  readonly message: string | null;
};

const initialState: AuthoringContractState = {
  phase: "disconnected",
  stored: null,
  message: null,
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const sameRequest = (left: RequestIdentity, right: RequestIdentity): boolean =>
  left.readExecutor === right.readExecutor &&
  left.connectedTarget === right.connectedTarget &&
  left.workspaceId === right.workspaceId &&
  left.revision === right.revision &&
  left.selectedStepId === right.selectedStepId;

export const useAuthoringContract = ({
  workspaceId,
  revision,
  selectedStepId,
}: UseAuthoringContractOptions): AuthoringContractController => {
  const { connectedTarget, readExecutor } = useConsoleWorkspace();
  const client = useMemo<AuthoringContractClient | null>(
    () => (readExecutor === null ? null : createAuthoringContractClient(readExecutor)),
    [readExecutor],
  );
  const request = useMemo<RequestIdentity | null>(
    () =>
      readExecutor !== null &&
      connectedTarget !== null &&
      workspaceId !== null &&
      revision !== null
        ? {
            readExecutor,
            connectedTarget,
            workspaceId,
            revision,
            selectedStepId: selectedStepId ?? null,
          }
        : null,
    [connectedTarget, readExecutor, revision, selectedStepId, workspaceId],
  );
  const [state, setState] = useState<AuthoringContractState>(initialState);
  const generationRef = useRef(0);

  const inspect = useCallback(
    (): void => {
      if (client === null || request === null) return;
      const generation = ++generationRef.current;
      const requested = request;
      setState((current) => ({
        phase: "loading",
        stored:
          current.stored !== null && sameRequest(current.stored.request, requested)
            ? current.stored
            : null,
        message: null,
      }));

      void client
        .inspect({
          workspaceId: requested.workspaceId,
          revision: requested.revision,
          selectedStepId: requested.selectedStepId,
        })
        .then((inventory) => {
          if (generation !== generationRef.current) return;
          setState({
            phase: "ready",
            stored: { request: requested, inventory },
            message: null,
          });
        })
        .catch((error: unknown) => {
          if (generation !== generationRef.current) return;
          setState((current) => ({
            ...current,
            phase: "error",
            message: errorMessage(error),
          }));
        });
    }, [client, request]);

  useEffect(() => {
    if (request === null || client === null) {
      generationRef.current++;
      setState({
        phase: client === null || connectedTarget === null ? "disconnected" : "idle",
        stored: null,
        message: null,
      });
      return;
    }
    inspect();
  }, [client, connectedTarget, inspect, request]);

  const refresh = useCallback((): void => {
    inspect();
  }, [inspect]);

  const currentInventory =
    request !== null && state.stored !== null && sameRequest(state.stored.request, request)
      ? state.stored.inventory
      : null;
  const phase =
    request !== null &&
    (state.stored === null || !sameRequest(state.stored.request, request))
      ? "loading"
      : request === null
        ? client === null || connectedTarget === null
          ? "disconnected"
          : "idle"
        : state.phase;

  return {
    phase,
    inventory: currentInventory,
    message: currentInventory === null && phase === "loading" ? null : state.message,
    refresh,
  };
};
