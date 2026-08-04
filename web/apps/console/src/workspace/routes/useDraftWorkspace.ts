import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createDraftWorkspaceClient,
  type DraftWorkspaceClient,
} from "../domain/draft-workspace-client.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";

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

type DraftWorkspaceState = Omit<DraftWorkspaceController, "refresh">;

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
  const previousWorkspaceIdRef = useRef(workspaceId);
  const currentWorkspaceIdRef = useRef(workspaceId);
  currentWorkspaceIdRef.current = workspaceId;

  const runList = useCallback(() => {
    if (!client || !connectedTarget) return;
    const generation = ++listGenerationRef.current;
    setState((current) => ({
      ...current,
      listPhase: "loading",
      listMessage: null,
    }));

    void client
      .list()
      .then((page) => {
        if (generation !== listGenerationRef.current) return;
        setState((current) => ({
          ...current,
          listPhase: "ready",
          items: page.items,
          listMessage: null,
        }));
      })
      .catch((error: unknown) => {
        if (generation !== listGenerationRef.current) return;
        setState((current) => ({
          ...current,
          listPhase: "error",
          listMessage: errorMessage(error),
        }));
      });
  }, [client, connectedTarget]);

  const runDetail = useCallback(
    (nextWorkspaceId: string | null) => {
      const generation = ++detailGenerationRef.current;
      if (!nextWorkspaceId) {
        setState((current) => ({
          ...current,
          detailPhase: client && connectedTarget ? "idle" : "disconnected",
          selected: null,
          detailMessage: null,
        }));
        return;
      }
      if (!client || !connectedTarget) {
        setState((current) => ({
          ...current,
          detailPhase: "disconnected",
          selected: null,
          detailMessage: null,
        }));
        return;
      }

      setState((current) => ({
        ...current,
        detailPhase: "loading",
        selected: null,
        detailMessage: null,
      }));

      void client
        .load(nextWorkspaceId)
        .then((detail) => {
          if (generation !== detailGenerationRef.current) return;
          setState((current) => ({
            ...current,
            detailPhase: "ready",
            selected: detail,
            detailMessage: null,
          }));
        })
        .catch((error: unknown) => {
          if (generation !== detailGenerationRef.current) return;
          setState((current) => ({
            ...current,
            detailPhase: "error",
            selected: null,
            detailMessage: errorMessage(error),
          }));
        });
    },
    [client, connectedTarget],
  );

  useEffect(() => {
    if (!client || !connectedTarget) {
      listGenerationRef.current++;
      detailGenerationRef.current++;
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

    // A new executor represents a fresh connection. Do not show data from the
    // old server while the list and URL-owned detail are being reloaded.
    setState((current) => ({
      ...current,
      items: [],
      selected: null,
      listMessage: null,
      detailMessage: null,
    }));
    runList();
    runDetail(currentWorkspaceIdRef.current);
  }, [client, connectedTarget, runDetail, runList]);

  useEffect(() => {
    if (previousWorkspaceIdRef.current === workspaceId) return;
    previousWorkspaceIdRef.current = workspaceId;
    runDetail(workspaceId);
  }, [runDetail, workspaceId]);

  const refresh = useCallback(() => {
    if (!client || !connectedTarget) return;
    runList();
    runDetail(workspaceId);
  }, [client, connectedTarget, runDetail, runList, workspaceId]);

  return { ...state, refresh };
};
