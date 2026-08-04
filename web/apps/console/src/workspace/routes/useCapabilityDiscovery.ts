import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsoleWorkspace } from "../context.js";
import {
  createCapabilityClient,
  type CapabilityClient,
} from "../domain/capability-client.js";
import type {
  CapabilityDetail,
  CapabilitySummary,
} from "../domain/capability-models.js";

const PAGE_LIMIT = 50;

export type CapabilityDiscoveryController = {
  readonly phase: "disconnected" | "loading" | "ready" | "error";
  readonly query: string;
  readonly sourceId: string;
  readonly items: ReadonlyArray<CapabilitySummary>;
  readonly selected: CapabilityDetail | null;
  readonly nextCursor: string | null;
  readonly message: string | null;
  readonly setQuery: (value: string) => void;
  readonly setSourceId: (value: string) => void;
  readonly search: () => void;
  readonly loadMore: () => void;
  readonly inspect: (qualifiedName: string) => void;
};

type DiscoveryState = Omit<CapabilityDiscoveryController, "setQuery" | "setSourceId" | "search" | "loadMore" | "inspect">;

type CapabilityFilters = {
  readonly query: string;
  readonly sourceId: string;
};

type DiscoveryStateWithAppliedFilters = DiscoveryState & {
  readonly appliedQuery: string;
  readonly appliedSourceId: string;
};

const initialState: DiscoveryStateWithAppliedFilters = {
  phase: "disconnected",
  query: "",
  sourceId: "",
  appliedQuery: "",
  appliedSourceId: "",
  items: [],
  selected: null,
  nextCursor: null,
  message: null,
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const requestParams = (
  query: string,
  sourceId: string,
  cursor?: string,
): { readonly query?: string; readonly sourceId?: string; readonly cursor?: string; readonly limit: number } => ({
  ...(query ? { query } : {}),
  ...(sourceId ? { sourceId } : {}),
  ...(cursor ? { cursor } : {}),
  limit: PAGE_LIMIT,
});

const appendUnique = (
  existing: ReadonlyArray<CapabilitySummary>,
  additions: ReadonlyArray<CapabilitySummary>,
): ReadonlyArray<CapabilitySummary> => {
  const names = new Set(existing.map((item) => item.name));
  const result = [...existing];
  for (const item of additions) {
    if (names.has(item.name)) continue;
    names.add(item.name);
    result.push(item);
  }
  return result;
};

export const useCapabilityDiscovery = (): CapabilityDiscoveryController => {
  const { connectedTarget, readExecutor } = useConsoleWorkspace();
  const client = useMemo<CapabilityClient | null>(
    () => (readExecutor ? createCapabilityClient(readExecutor) : null),
    [readExecutor],
  );
  const [state, setState] = useState<DiscoveryStateWithAppliedFilters>(initialState);
  const listGenerationRef = useRef(0);
  const inspectGenerationRef = useRef(0);

  const runList = useCallback(
    (filters: CapabilityFilters, cursor: string | undefined, append: boolean): void => {
      if (!client) return;
      const generation = ++listGenerationRef.current;
      if (append === false) inspectGenerationRef.current++;
      setState((current) => ({
        ...current,
        appliedQuery: filters.query,
        appliedSourceId: filters.sourceId,
        phase: "loading",
        items: append ? current.items : [],
        selected: append ? current.selected : null,
        nextCursor: append ? current.nextCursor : null,
        message: null,
      }));

      void client
        .list(requestParams(filters.query, filters.sourceId, cursor))
        .then((page) => {
          if (generation !== listGenerationRef.current) return;
          setState((current) => ({
            ...current,
            phase: "ready",
            items: appendUnique(append ? current.items : [], page.capabilities),
            nextCursor: page.nextCursor,
            message: null,
          }));
        })
        .catch((error: unknown) => {
          if (generation !== listGenerationRef.current) return;
          setState((current) => ({
            ...current,
            phase: "error",
            message: errorMessage(error),
          }));
        });
    },
    [client],
  );

  useEffect(() => {
    if (!client || !connectedTarget) {
      listGenerationRef.current++;
      inspectGenerationRef.current++;
      setState((current) => ({
        ...current,
        phase: "disconnected",
        items: [],
        selected: null,
        nextCursor: null,
        message: null,
      }));
      return;
    }

    runList({ query: state.query, sourceId: state.sourceId }, undefined, false);
    // The executor identity changes with the connected target. Query and source
    // filters are intentionally retained so reconnecting preserves the view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, connectedTarget, runList]);

  const setQuery = useCallback((query: string) => {
    setState((current) => ({ ...current, query }));
  }, []);

  const setSourceId = useCallback(
    (sourceId: string) => {
      setState((current) => ({ ...current, sourceId }));
    },
    [],
  );

  const search = useCallback(() => {
    runList({ query: state.query, sourceId: state.sourceId }, undefined, false);
  }, [runList, state.query, state.sourceId]);

  const loadMore = useCallback(() => {
    if (!state.nextCursor || state.phase === "loading") return;
    runList(
      { query: state.appliedQuery, sourceId: state.appliedSourceId },
      state.nextCursor,
      true,
    );
  }, [
    runList,
    state.appliedQuery,
    state.appliedSourceId,
    state.nextCursor,
    state.phase,
  ]);

  const inspect = useCallback(
    (qualifiedName: string) => {
      if (!client) return;
      const generation = ++inspectGenerationRef.current;
      setState((current) => ({ ...current, phase: "loading", selected: null, message: null }));
      void client
        .inspect(qualifiedName)
        .then((detail) => {
          if (generation !== inspectGenerationRef.current) return;
          setState((current) => ({ ...current, phase: "ready", selected: detail, message: null }));
        })
        .catch((error: unknown) => {
          if (generation !== inspectGenerationRef.current) return;
          setState((current) => ({ ...current, phase: "error", message: errorMessage(error) }));
        });
    },
    [client],
  );

  return {
    ...state,
    setQuery,
    setSourceId,
    search,
    loadMore,
    inspect,
  };
};
