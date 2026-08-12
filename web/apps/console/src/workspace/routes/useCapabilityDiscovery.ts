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
import type { ConsoleReadExecutor } from "../domain/read-executor.js";

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

export type CapabilityDiscoveryOptions = {
  readonly loadAllPages?: boolean;
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

type ConnectionProvenance = {
  readonly readExecutor: ConsoleReadExecutor;
  readonly connectedTarget: string;
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

const isSameConnection = (
  left: ConnectionProvenance | null,
  right: ConnectionProvenance | null,
): boolean => {
  if (left === null || right === null) return left === right;
  return left.readExecutor === right.readExecutor && left.connectedTarget === right.connectedTarget;
};

export const useCapabilityDiscovery = (
  { loadAllPages = false }: CapabilityDiscoveryOptions = {},
): CapabilityDiscoveryController => {
  const { connectedTarget, readExecutor } = useConsoleWorkspace();
  const client = useMemo<CapabilityClient | null>(
    () => (readExecutor ? createCapabilityClient(readExecutor) : null),
    [readExecutor],
  );
  const [state, setState] = useState<DiscoveryStateWithAppliedFilters>(initialState);
  const listGenerationRef = useRef(0);
  const inspectGenerationRef = useRef(0);
  const automaticPageCursorsRef = useRef<Set<string>>(new Set());
  const committedProvenanceRef = useRef<ConnectionProvenance | null>(null);
  const listProvenanceRef = useRef<ConnectionProvenance | null>(null);
  const selectedProvenanceRef = useRef<ConnectionProvenance | null>(null);
  const currentProvenance = useMemo<ConnectionProvenance | null>(
    () =>
      readExecutor !== null && connectedTarget !== null
        ? { readExecutor, connectedTarget }
        : null,
    [connectedTarget, readExecutor],
  );

  const runList = useCallback(
    (filters: CapabilityFilters, cursor: string | undefined, append: boolean): void => {
      if (!client || currentProvenance === null) return;
      const requestProvenance = currentProvenance;
      const generation = ++listGenerationRef.current;
      if (append === false) {
        inspectGenerationRef.current++;
        automaticPageCursorsRef.current.clear();
      }
      listProvenanceRef.current = requestProvenance;
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
          if (
            generation !== listGenerationRef.current ||
            !isSameConnection(requestProvenance, committedProvenanceRef.current)
          ) return;
          setState((current) => ({
            ...current,
            phase: "ready",
            items: appendUnique(append ? current.items : [], page.capabilities),
            nextCursor: page.nextCursor,
            message: null,
          }));
        })
        .catch((error: unknown) => {
          if (
            generation !== listGenerationRef.current ||
            !isSameConnection(requestProvenance, committedProvenanceRef.current)
          ) return;
          setState((current) => ({
            ...current,
            phase: "error",
            message: errorMessage(error),
          }));
        });
    },
    [client, currentProvenance],
  );

  useEffect(() => {
    committedProvenanceRef.current = currentProvenance;
    if (!client || !connectedTarget) {
      listGenerationRef.current++;
      inspectGenerationRef.current++;
      listProvenanceRef.current = null;
      selectedProvenanceRef.current = null;
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

    runList(
      { query: state.appliedQuery, sourceId: state.appliedSourceId },
      undefined,
      false,
    );
    // The executor identity changes with the connected target. Query and source
    // filters are intentionally retained so reconnecting preserves the submitted view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, connectedTarget, currentProvenance, readExecutor, runList]);

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

  useEffect(() => {
    if (!loadAllPages || state.phase !== "ready" || state.nextCursor === null) return;
    if (automaticPageCursorsRef.current.has(state.nextCursor)) return;
    automaticPageCursorsRef.current.add(state.nextCursor);
    // Authoring palettes need the complete catalog because they do not expose
    // discovery pagination. Stop when a server repeats a cursor rather than
    // hiding an infinite request loop behind item deduplication.
    loadMore();
  }, [loadAllPages, loadMore, state.nextCursor, state.phase]);

  const inspect = useCallback(
    (qualifiedName: string) => {
      if (!client) return;
      if (currentProvenance === null) return;
      const generation = ++inspectGenerationRef.current;
      const requestProvenance = currentProvenance;
      selectedProvenanceRef.current = null;
      setState((current) => ({ ...current, phase: "loading", selected: null, message: null }));
      void client
        .inspect(qualifiedName)
        .then((detail) => {
          if (
            generation !== inspectGenerationRef.current ||
            !isSameConnection(requestProvenance, committedProvenanceRef.current)
          ) return;
          selectedProvenanceRef.current = requestProvenance;
          setState((current) => ({ ...current, phase: "ready", selected: detail, message: null }));
        })
        .catch((error: unknown) => {
          if (
            generation !== inspectGenerationRef.current ||
            !isSameConnection(requestProvenance, committedProvenanceRef.current)
          ) return;
          setState((current) => ({ ...current, phase: "error", message: errorMessage(error) }));
        });
    },
    [client, currentProvenance],
  );

  const hasCurrentList = isSameConnection(
    listProvenanceRef.current,
    currentProvenance,
  );
  const hasCurrentSelection = isSameConnection(
    selectedProvenanceRef.current,
    currentProvenance,
  );
  const visiblePhase =
    currentProvenance === null
      ? "disconnected"
      : hasCurrentList
        ? state.phase
        : "loading";

  return {
    ...state,
    phase: visiblePhase,
    items: hasCurrentList ? state.items : [],
    selected: hasCurrentSelection ? state.selected : null,
    nextCursor: hasCurrentList ? state.nextCursor : null,
    message: hasCurrentList ? state.message : null,
    setQuery,
    setSourceId,
    search,
    loadMore,
    inspect,
  };
};
