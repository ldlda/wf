import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftWorkspaceClient,
  type DraftWorkspaceClient,
} from "../domain/draft-workspace-client.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";

export type DraftLoadPhase =
  | "disconnected"
  | "idle"
  | "loading"
  | "ready"
  | "error";

export type DraftWorkspaceController = {
  readonly listPhase: DraftLoadPhase;
  readonly detailPhase: DraftLoadPhase;
  readonly items: ReadonlyArray<DraftWorkspace>;
  readonly selected: DraftWorkspace | null;
  readonly listMessage: string | null;
  readonly detailMessage: string | null;
  readonly refresh: () => void;
};

type StoredDraftSelection = {
  readonly workspace: DraftWorkspace;
  readonly workspaceId: string;
  readonly connectedTarget: string;
  readonly readExecutor: ConsoleReadExecutor;
};

type DraftReadProvenance = {
  readonly readExecutor: ConsoleReadExecutor;
  readonly connectedTarget: string;
};

type DraftWorkspaceState = Omit<DraftWorkspaceController, "refresh" | "selected"> & {
  readonly selected: StoredDraftSelection | null;
};

const initialState: DraftWorkspaceState = {
  listPhase: "disconnected",
  detailPhase: "disconnected",
  items: [],
  selected: null,
  listMessage: null,
  detailMessage: null,
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const isCurrentProvenance = (
  current: DraftReadProvenance | null,
  request: DraftReadProvenance,
): boolean =>
  current !== null &&
  request.readExecutor === current.readExecutor &&
  request.connectedTarget === current.connectedTarget;

export const useDraftWorkspace = (
  workspaceId: string | null,
): DraftWorkspaceController => {
  const { connectedTarget, readExecutor } = useConsoleWorkspace();
  const client = useMemo<DraftWorkspaceClient | null>(
    () => (readExecutor ? createDraftWorkspaceClient(readExecutor) : null),
    [readExecutor],
  );
  const [state, setState] = useState<DraftWorkspaceState>(initialState);
  const listGenerationRef = useRef(0);
  const detailGenerationRef = useRef(0);
  const listPendingRef = useRef(false);
  const detailPendingRef = useRef(false);
  const observedRequestRef = useRef<{
    readonly readExecutor: ConsoleReadExecutor | null;
    readonly connectedTarget: string | null;
    readonly workspaceId: string | null;
  } | null>(null);
  const listProvenanceRef = useRef<DraftReadProvenance | null>(null);
  const committedProvenanceRef = useRef<DraftReadProvenance | null>(null);

  const currentProvenance = useMemo<DraftReadProvenance | null>(
    () =>
      readExecutor !== null && connectedTarget !== null
        ? {
            readExecutor,
            connectedTarget,
          }
        : null,
    [connectedTarget, readExecutor],
  );

  const runList = useCallback((force = false) => {
    if (!client || currentProvenance === null) return;
    if (listPendingRef.current && !force) return;
    listPendingRef.current = false;
    const generation = ++listGenerationRef.current;
    const requestProvenance = currentProvenance;
    listProvenanceRef.current = requestProvenance;
    listPendingRef.current = true;
    setState((current) => ({
      ...current,
      listPhase: "loading",
      listMessage: null,
    }));

    void client
      .list()
      .then((page) => {
        if (
          generation !== listGenerationRef.current ||
          !isCurrentProvenance(committedProvenanceRef.current, requestProvenance)
        ) return;
        setState((current) => ({
          ...current,
          listPhase: "ready",
          items: page.items,
          listMessage: null,
        }));
      })
      .catch((error: unknown) => {
        if (
          generation !== listGenerationRef.current ||
          !isCurrentProvenance(committedProvenanceRef.current, requestProvenance)
        ) return;
        setState((current) => ({
          ...current,
          listPhase: "error",
          listMessage: errorMessage(error),
        }));
      })
      .finally(() => {
        if (generation === listGenerationRef.current) listPendingRef.current = false;
      });
  }, [client, currentProvenance]);

  const runDetail = useCallback(
    (nextWorkspaceId: string | null, force = false) => {
      if (detailPendingRef.current && !force) return;
      detailPendingRef.current = false;
      const generation = ++detailGenerationRef.current;
      if (!nextWorkspaceId) {
        detailPendingRef.current = false;
        setState((current) => ({
          ...current,
          detailPhase: client && connectedTarget ? "idle" : "disconnected",
          selected: null,
          detailMessage: null,
        }));
        return;
      }
      if (!client || !connectedTarget) {
        detailPendingRef.current = false;
        setState((current) => ({
          ...current,
          detailPhase: "disconnected",
          selected: null,
          detailMessage: null,
        }));
        return;
      }

      const requestTarget = connectedTarget;
      const requestProvenance = currentProvenance;
      detailPendingRef.current = true;
      setState((current) => ({
        ...current,
        detailPhase: "loading",
        selected: null,
        detailMessage: null,
      }));

      void client
        .load(nextWorkspaceId)
        .then((detail) => {
          if (
            generation !== detailGenerationRef.current ||
            requestProvenance === null ||
            !isCurrentProvenance(committedProvenanceRef.current, requestProvenance)
          ) return;
          setState((current) => ({
            ...current,
            detailPhase: "ready",
            selected: {
              workspace: detail,
              workspaceId: nextWorkspaceId,
              connectedTarget: requestTarget,
              readExecutor: requestProvenance.readExecutor,
            },
            detailMessage: null,
          }));
        })
        .catch((error: unknown) => {
          if (
            generation !== detailGenerationRef.current ||
            requestProvenance === null ||
            !isCurrentProvenance(committedProvenanceRef.current, requestProvenance)
          ) return;
          setState((current) => ({
            ...current,
            detailPhase: "error",
            selected: null,
            detailMessage: errorMessage(error),
          }));
        })
        .finally(() => {
          if (generation === detailGenerationRef.current) detailPendingRef.current = false;
        });
    },
    [client, connectedTarget, currentProvenance],
  );

  useEffect(() => {
    committedProvenanceRef.current = currentProvenance;
    const previousRequest = observedRequestRef.current;
    const connectionChanged =
      previousRequest === null ||
      previousRequest.readExecutor !== readExecutor ||
      previousRequest.connectedTarget !== connectedTarget;
    const workspaceChanged =
      previousRequest !== null && previousRequest.workspaceId !== workspaceId;
    observedRequestRef.current = { readExecutor, connectedTarget, workspaceId };

    if (!client || !connectedTarget) {
      listGenerationRef.current++;
      detailGenerationRef.current++;
      listPendingRef.current = false;
      detailPendingRef.current = false;
      listProvenanceRef.current = null;
      setState((current) => ({
        ...current,
        listPhase: "disconnected",
        detailPhase: "disconnected",
        items: [],
        selected: null,
        listMessage: null,
        detailMessage: null,
      }));
      return;
    }

    if (connectionChanged) {
      // A new executor represents a fresh connection. Do not show data from
      // the old server while the combined URL-owned reads are reloading.
      listGenerationRef.current++;
      detailGenerationRef.current++;
      listPendingRef.current = false;
      detailPendingRef.current = false;
      setState((current) => ({
        ...current,
        items: [],
        selected: null,
        listMessage: null,
        detailMessage: null,
      }));
      runList(true);
      runDetail(workspaceId, true);
    } else if (workspaceChanged) {
      runDetail(workspaceId, true);
    }
  }, [client, connectedTarget, currentProvenance, readExecutor, runDetail, runList, workspaceId]);

  const refresh = useCallback(() => {
    if (!client || !connectedTarget) return;
    runList();
    runDetail(workspaceId);
  }, [client, connectedTarget, runDetail, runList, workspaceId]);

  const storedSelection = state.selected;
  const selected =
    storedSelection !== null &&
    workspaceId !== null &&
    connectedTarget !== null &&
    storedSelection.workspaceId === workspaceId &&
    storedSelection.connectedTarget === connectedTarget &&
    storedSelection.readExecutor === readExecutor
      ? storedSelection.workspace
      : null;

  const hasCurrentList =
    currentProvenance !== null &&
    listProvenanceRef.current !== null &&
    isCurrentProvenance(currentProvenance, listProvenanceRef.current);
  const visibleListPhase =
    currentProvenance === null
      ? "disconnected"
      : hasCurrentList
        ? state.listPhase
        : "loading";
  const visibleDetailPhase =
    currentProvenance === null
      ? "disconnected"
      : storedSelection !== null && selected === null
        ? "loading"
        : state.detailPhase;

  return {
    ...state,
    listPhase: visibleListPhase,
    detailPhase: visibleDetailPhase,
    items: hasCurrentList ? state.items : [],
    listMessage: hasCurrentList ? state.listMessage : null,
    selected,
    refresh,
  };
};
